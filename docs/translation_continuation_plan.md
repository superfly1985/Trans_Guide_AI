# 翻译截断处理与断点续传方案文档

## 背景

当前系统在处理大文件翻译时，由于 LLM 的 `max_tokens` 限制，经常出现响应被截断的情况。例如：
- 文件包含 446 个文本块
- 只成功翻译了 223 个块（50%）
- 剩余 223 个块未翻译

需要实现智能的截断检测和断点续传机制。

---

## 功能 1：截断后批次大小调整到设置的 80%

### 需求描述

当检测到 LLM 响应被截断时，将后续批次的大小调整为用户设置值的 80%，且只调整一次。

### 实现方案

#### 前端修改

**1. 记录原始批次大小**
```javascript
// 在 translateFile 函数开始时记录
const USER_BATCH_SIZE = parseInt(elements.batchSize.value) || 60000;
let currentBatchSize = USER_BATCH_SIZE;
let hasAdjustedBatchSize = false; // 标记是否已调整过
```

**2. 截断检测逻辑**
```javascript
// 当完成率 < 90% 时认为是截断
if (completionRate < 0.9 && !hasAdjustedBatchSize) {
    // 调整到 80%
    currentBatchSize = Math.floor(USER_BATCH_SIZE * 0.8);
    hasAdjustedBatchSize = true;
    console.log(`[LLM链路] 检测到截断，批次大小调整为 ${currentBatchSize}`);
}
```

**3. 后续批次使用调整后的值**
```javascript
// 重新分批次（使用调整后的 currentBatchSize）
const remainingBlocks = allBlocks.slice(completedCount);
const newBatches = createBatches(remainingBlocks, currentBatchSize);
```

---

## 功能 2：断点续传（方案 B）

### 需求描述

当批次翻译被截断时，不是重试整个批次，而是识别出已翻译的块和未翻译的块，只将未翻译的块作为新批次继续发送。

### 实现方案

#### 后端增强

**1. 修改 `/api/translate/batch` 接口**

添加可选参数 `start_index`，用于指定批次中第一个块的实际索引：

```python
@app.route('/api/translate/batch', methods=['POST'])
@login_required
def translate_batch():
    data = request.json
    texts = data.get('texts', [])
    start_index = data.get('start_index', 0)  # 新增参数
    
    # ... 翻译逻辑 ...
    
    # 返回结果时，索引需要加上 start_index 偏移
    translations = []
    for i, trans in enumerate(raw_translations):
        translations.append({
            'index': i + start_index,  # 应用偏移
            'translation': trans
        })
    
    # 新增：返回最后成功翻译的块索引，帮助前端识别断点
    last_translated_index = len(raw_translations) - 1 + start_index
    
    return jsonify({
        'success': True,
        'translations': translations,
        'last_index': last_translated_index,  # 新增字段
        'expected_count': len(texts),
        'actual_count': len(raw_translations)
    })
```

**2. 返回字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `translations` | array | 翻译结果数组 |
| `last_index` | int | 最后成功翻译的块索引 |
| `expected_count` | int | 期望翻译的块数量 |
| `actual_count` | int | 实际翻译的块数量 |

#### 前端修改

**1. 修改请求体构建**

```javascript
const requestBody = { 
    texts: currentBatch.map((b, i) => {
        const numericIndex = i;
        indexMapping[numericIndex] = b.index;
        return { 
            index: numericIndex, 
            text: b.text 
        };
    }),
    start_index: 0  // 默认从 0 开始
};
```

**2. 断点续传逻辑**

```javascript
if (data.success && data.translations) {
    const expectedCount = currentBatch.length;
    const actualCount = data.translations.length;
    const completionRate = actualCount / expectedCount;
    
    // 更新已翻译的块
    for (const trans of data.translations) {
        const originalIndex = indexMapping[trans.index];
        if (originalIndex !== undefined) {
            state.translations[originalIndex] = trans.translation;
            // 更新预览...
        }
    }
    
    // 断点续传：处理未翻译的块
    if (completionRate < 1.0 && actualCount < expectedCount) {
        // 从 last_index + 1 开始继续
        const lastTranslatedIndex = data.last_index;  // 后端返回
        const remainingInBatch = currentBatch.slice(actualCount);
        
        if (remainingInBatch.length > 0) {
            console.log(`[LLM链路] 断点续传：${actualCount}/${expectedCount} 完成，剩余 ${remainingInBatch.length} 个块`);
            
            // 构建续传请求
            const continuationBody = {
                texts: remainingInBatch.map((b, i) => ({
                    index: i,
                    text: b.text
                })),
                start_index: actualCount  // 告诉后端索引偏移
            };
            
            // 将续传请求插入队列（优先处理）
            pendingContinuations.push({
                body: continuationBody,
                indexMapping: remainingInBatch.map((b, i) => b.index)
            });
        }
    }
    
    completed += actualCount;
}
```

**3. 续传队列处理**

```javascript
// 处理所有续传请求
while (pendingContinuations.length > 0) {
    const continuation = pendingContinuations.shift();
    await processContinuation(continuation);
}
```

---

## 时序图

```
前端                                后端
 |                                   |
 |--- 批次 1 (块 0-49) ------------->|
 |                                   |
 |<-- 返回 30 个块 (last_index=29) --|
 |                                   |
 |--- 续传 (块 30-49, start=30) ---->|
 |                                   |
 |<-- 返回 20 个块 (last_index=49) --|
 |                                   |
 |--- 批次 2 (块 50-99) ------------>|
 |                                   |
 |<-- 返回 50 个块 (last_index=99) --|
 |                                   |
 |--- 批次 3 (块 100-149) ---------->|
 |                                   |
 |<-- 返回 25 个块 (last_index=124) -|
 |                                   |
 |--- 续传 (块 25-49, start=25) ---->|
 |                                   |
 |<-- 返回 25 个块 (last_index=149) -|
 |                                   |
```

---

## 配置项

在 `config.json` 中添加：

```json
{
    "translation": {
        "batch_size_adjustment": 0.8,
        "min_completion_rate": 0.9,
        "enable_continuation": true
    }
}
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 后端索引计算错误 | 中 | 高 | 添加单元测试验证索引映射 |
| 无限续传循环 | 低 | 高 | 设置最大续传次数（如 3 次） |
| 性能下降 | 低 | 中 | 续传批次优先处理，避免队列过长 |

---

## 实施计划

1. **Phase 1**：功能 1（批次大小调整）
   - 修改前端：1 小时
   - 测试：30 分钟

2. **Phase 2**：功能 2 后端增强
   - 修改 `/api/translate/batch`：1 小时
   - 添加单元测试：1 小时

3. **Phase 3**：功能 2 前端实现
   - 修改批次处理逻辑：2 小时
   - 添加续传队列：1 小时
   - 测试：1 小时

**总计：约 7.5 小时**

---

## 版本历史

| 版本 | 日期 | 作者 | 说明 |
|------|------|------|------|
| v1.0 | 2026-04-28 | AI Assistant | 初始版本 |

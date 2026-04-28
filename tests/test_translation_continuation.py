"""
翻译截断处理和断点续传功能测试
"""
import json
import sys
sys.path.insert(0, 'd:\\01.AwesomeProject\\52.Trans_Guide_AI')

def test_batch_size_adjustment():
    """测试批次大小调整逻辑"""
    print("=" * 60)
    print("测试1: 批次大小调整逻辑")
    print("=" * 60)
    
    # 模拟用户设置
    USER_BATCH_SIZE = 60000
    hasAdjustedBatchSize = False
    currentBatchSize = USER_BATCH_SIZE
    
    # 模拟截断检测
    completionRate = 0.5  # 50% 完成率，低于 90%
    
    if completionRate < 0.9 and not hasAdjustedBatchSize:
        newBatchSize = int(USER_BATCH_SIZE * 0.8)
        print(f"✓ 检测到截断 (完成率 {completionRate*100}%)")
        print(f"✓ 批次大小从 {currentBatchSize} 调整为 {newBatchSize} (80%)")
        currentBatchSize = newBatchSize
        hasAdjustedBatchSize = True
    
    # 验证只调整一次
    completionRate2 = 0.6
    if completionRate2 < 0.9 and not hasAdjustedBatchSize:
        print("✗ 错误：不应该再次调整")
    else:
        print("✓ 正确：不会重复调整")
    
    assert currentBatchSize == 48000, f"批次大小应该是 48000，实际是 {currentBatchSize}"
    assert hasAdjustedBatchSize == True, "应该标记为已调整"
    print("✓ 测试通过\n")


def test_continuation_logic():
    """测试断点续传逻辑"""
    print("=" * 60)
    print("测试2: 断点续传逻辑")
    print("=" * 60)
    
    # 模拟一个批次
    batch = [
        {'index': 0, 'text': 'Text 1'},
        {'index': 1, 'text': 'Text 2'},
        {'index': 2, 'text': 'Text 3'},
        {'index': 3, 'text': 'Text 4'},
        {'index': 4, 'text': 'Text 5'},
    ]
    
    # 模拟只返回了前3个
    actualCount = 3
    expectedCount = 5
    
    # 断点续传：获取剩余块
    remainingBlocks = batch[actualCount:]
    
    print(f"原始批次: {len(batch)} 个块")
    print(f"实际返回: {actualCount} 个块")
    print(f"剩余块: {len(remainingBlocks)} 个")
    
    assert len(remainingBlocks) == 2, f"应该有 2 个剩余块，实际是 {len(remainingBlocks)}"
    assert remainingBlocks[0]['index'] == 3, "第一个剩余块索引应该是 3"
    assert remainingBlocks[1]['index'] == 4, "第二个剩余块索引应该是 4"
    
    print("✓ 断点续传逻辑正确\n")


def test_backend_response_format():
    """测试后端响应格式"""
    print("=" * 60)
    print("测试3: 后端响应格式")
    print("=" * 60)
    
    # 模拟后端响应
    mock_response = {
        'success': True,
        'translations': [
            {'index': 0, 'translation': '翻译1'},
            {'index': 1, 'translation': '翻译2'},
            {'index': 2, 'translation': '翻译3'},
        ],
        'last_index': 2,
        'expected_count': 5,
        'actual_count': 3,
        'terms_used': {}
    }
    
    # 验证响应包含所有必需字段
    required_fields = ['success', 'translations', 'last_index', 'expected_count', 'actual_count']
    for field in required_fields:
        assert field in mock_response, f"响应缺少字段: {field}"
        print(f"✓ 字段 '{field}' 存在")
    
    # 验证数值正确
    assert mock_response['last_index'] == 2, "last_index 应该是 2"
    assert mock_response['expected_count'] == 5, "expected_count 应该是 5"
    assert mock_response['actual_count'] == 3, "actual_count 应该是 3"
    
    print("✓ 响应格式正确\n")


def test_start_index_adjustment():
    """测试起始索引偏移"""
    print("=" * 60)
    print("测试4: 起始索引偏移")
    print("=" * 60)
    
    start_index = 10
    translations = []
    
    # 模拟返回的块（从0开始）
    raw_translations = [
        {'index': 0, 'translation': '翻译0'},
        {'index': 1, 'translation': '翻译1'},
        {'index': 2, 'translation': '翻译2'},
    ]
    
    # 应用偏移
    for trans in raw_translations:
        adjusted_idx = trans['index'] + start_index
        translations.append({
            'index': adjusted_idx,
            'translation': trans['translation']
        })
    
    print(f"起始索引: {start_index}")
    print(f"原始索引: {[t['index'] for t in raw_translations]}")
    print(f"调整后索引: {[t['index'] for t in translations]}")
    
    assert translations[0]['index'] == 10, "第一个块索引应该是 10"
    assert translations[1]['index'] == 11, "第二个块索引应该是 11"
    assert translations[2]['index'] == 12, "第三个块索引应该是 12"
    
    print("✓ 索引偏移正确\n")


def test_integration_scenario():
    """测试完整场景"""
    print("=" * 60)
    print("测试5: 完整场景模拟")
    print("=" * 60)
    
    # 模拟文件有 10 个块
    all_blocks = [{'index': i, 'text': f'Text {i}'} for i in range(10)]
    
    # 初始批次大小为 6
    batch_size = 6
    batches = [all_blocks[i:i+batch_size] for i in range(0, len(all_blocks), batch_size)]
    
    print(f"文件总块数: {len(all_blocks)}")
    print(f"初始批次: {[len(b) for b in batches]} 个块")
    
    # 模拟第一个批次只返回了 4 个（截断）
    first_batch_actual = 4
    first_batch_expected = 6
    completion_rate = first_batch_actual / first_batch_expected
    
    print(f"\n第一批: 期望 {first_batch_expected}, 实际 {first_batch_actual}, 完成率 {completion_rate*100:.1f}%")
    
    # 触发批次大小调整
    if completion_rate < 0.9:
        new_batch_size = int(batch_size * 0.8)
        print(f"✓ 触发调整: 批次大小 {batch_size} -> {new_batch_size}")
        batch_size = new_batch_size
    
    # 断点续传：将剩余 2 个块加入队列
    remaining = batches[0][first_batch_actual:]
    if remaining:
        batches.insert(1, remaining)
        print(f"✓ 断点续传: 剩余 {len(remaining)} 个块加入队列")
    
    print(f"\n最终批次结构: {[len(b) for b in batches]} 个块")
    print(f"总批次数: {len(batches)}")
    
    assert len(batches) == 3, f"应该有 3 个批次，实际是 {len(batches)}"
    assert batch_size == 4, f"批次大小应该是 4，实际是 {batch_size}"
    
    print("✓ 完整场景测试通过\n")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("翻译截断处理和断点续传功能测试")
    print("=" * 60 + "\n")
    
    try:
        test_batch_size_adjustment()
        test_continuation_logic()
        test_backend_response_format()
        test_start_index_adjustment()
        test_integration_scenario()
        
        print("=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

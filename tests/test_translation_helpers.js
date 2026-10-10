const assert = require('assert');
const helpers = require('../web/static/translation_helpers.js');

const mostlyEnglishBlocks = [
  { text: 'PROBLEM SOLVING SHEET' },
  { text: 'Root cause' },
  { text: 'Corrective action' },
  { text: 'Start date' },
  { text: 'Closing date' }
];

const mostlyChineseBlocks = [
  { text: '问题解决表' },
  { text: '根本原因' },
  { text: '纠正措施' },
  { text: '开始日期' },
  { text: '关闭日期' }
];

assert.deepStrictEqual(
  helpers.getDirectionMismatchWarning(mostlyEnglishBlocks, 'zh2en'),
  {
    detected: 'english',
    recommendedDirection: 'en2zh',
    message: '检测到当前文档主要为英文，当前翻译方向是“中译英”。建议切换为“英译中”。'
  }
);

assert.strictEqual(
  helpers.getDirectionMismatchWarning(mostlyEnglishBlocks, 'en2zh'),
  null
);

assert.deepStrictEqual(
  helpers.getDirectionMismatchWarning(mostlyChineseBlocks, 'en2zh'),
  {
    detected: 'chinese',
    recommendedDirection: 'zh2en',
    message: '检测到当前文档主要为中文，当前翻译方向是“英译中”。建议切换为“中译英”。'
  }
);

assert.strictEqual(
  helpers.calculateCompletedCount(
    20,
    [
      { index: 0, translation: 'a' },
      { index: 0, translation: 'duplicate' },
      { index: 1, translation: 'b' },
      { index: 99, translation: 'outside batch' }
    ],
    { 0: 240, 1: 241 },
    268
  ),
  22
);

console.log('translation helper tests passed');

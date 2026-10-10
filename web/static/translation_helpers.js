(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.TransGuideHelpers = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    function countLanguageChars(text) {
        const value = String(text || '');
        const chineseMatches = value.match(/[\u4e00-\u9fff]/g) || [];
        const englishMatches = value.match(/[A-Za-z]/g) || [];
        return {
            chinese: chineseMatches.length,
            english: englishMatches.length
        };
    }

    function detectDominantLanguage(blocks, sampleSize) {
        const sample = (blocks || [])
            .filter(block => block && String(block.text || '').trim())
            .slice(0, sampleSize || 50);

        let chinese = 0;
        let english = 0;
        for (const block of sample) {
            const counts = countLanguageChars(block.text);
            chinese += counts.chinese;
            english += counts.english;
        }

        const total = chinese + english;
        if (!total) {
            return { language: 'unknown', confidence: 0, chinese, english };
        }

        if (english / total >= 0.8) {
            return { language: 'english', confidence: english / total, chinese, english };
        }
        if (chinese / total >= 0.8) {
            return { language: 'chinese', confidence: chinese / total, chinese, english };
        }
        return {
            language: 'mixed',
            confidence: Math.max(chinese, english) / total,
            chinese,
            english
        };
    }

    function getDirectionMismatchWarning(blocks, direction) {
        const detected = detectDominantLanguage(blocks);
        if (direction === 'zh2en' && detected.language === 'english') {
            return {
                detected: 'english',
                recommendedDirection: 'en2zh',
                message: '检测到当前文档主要为英文，当前翻译方向是“中译英”。建议切换为“英译中”。'
            };
        }
        if (direction === 'en2zh' && detected.language === 'chinese') {
            return {
                detected: 'chinese',
                recommendedDirection: 'zh2en',
                message: '检测到当前文档主要为中文，当前翻译方向是“英译中”。建议切换为“中译英”。'
            };
        }
        return null;
    }

    function getUniqueValidTranslationIndexes(translations, indexMapping) {
        const validIndexes = new Set();
        const mapping = indexMapping || {};
        for (const trans of translations || []) {
            if (!trans) continue;
            const originalIndex = mapping[trans.index];
            if (originalIndex !== undefined) {
                validIndexes.add(originalIndex);
            }
        }
        return validIndexes;
    }

    function calculateCompletedCount(currentCompleted, translations, indexMapping, total) {
        const increment = getUniqueValidTranslationIndexes(translations, indexMapping).size;
        return Math.min(total, currentCompleted + increment);
    }

    return {
        calculateCompletedCount,
        detectDominantLanguage,
        getDirectionMismatchWarning,
        getUniqueValidTranslationIndexes
    };
}));

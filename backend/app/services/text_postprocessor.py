import re
from typing import List, Tuple, Dict, Any

class PostprocessingRule:
    name: str = "BaseRule"
    description: str = ""

    def apply(self, text: str) -> Tuple[str, bool, List[str]]:
        """
        Applies rule to text.
        Returns: (new_text, was_modified, list_of_change_descriptions)
        """
        raise NotImplementedError


class QuantityMultiplierRule(PostprocessingRule):
    name = "Quantity Multiplier Repair"
    description = "Converts OCR confusion Ix, lx, IX at quantity position to 1x"

    def apply(self, text: str) -> Tuple[str, bool, List[str]]:
        changes = []
        # Match 'Ix', 'IX', 'lx', 'Ix ' at word boundary
        # e.g., 'Ix Aqua Frizzante' -> '1x Aqua Frizzante', 'Ix Pizza' -> '1x Pizza'
        pattern = r'(?i)\b[il]x\b'
        
        def replacer(match):
            original = match.group(0)
            changes.append(f"Fixed quantity multiplier '{original}' -> '1x'")
            return "1x"

        new_text = re.sub(pattern, replacer, text)
        return new_text, len(changes) > 0, changes


class MetricUnitRule(PostprocessingRule):
    name = "Metric Unit Normalizer"
    description = "Fixes digit 1 misread as letter I or l in units like Ikg, Iml, Ig, Il"

    def apply(self, text: str) -> Tuple[str, bool, List[str]]:
        changes = []
        # Match 'Ikg', 'lkg', 'Iml', 'lml', 'Ig', 'lg', 'Il', 'll', 'Istk', 'Ipck'
        # e.g., 'Bio Apple Ikg' -> 'Bio Apple 1kg', 'Juice 2Il' -> 'Juice 21l'
        pattern = r'(?i)\b[il](kg|g|mg|ml|l|stk|pck|pcs)\b'

        def replacer(match):
            original = match.group(0)
            unit = match.group(1).lower()
            fixed = f"1{unit}"
            changes.append(f"Fixed unit quantity '{original}' -> '{fixed}'")
            return fixed

        new_text = re.sub(pattern, replacer, text)
        return new_text, len(changes) > 0, changes


class AlphanumericContextRule(PostprocessingRule):
    name = "Alphanumeric Price & Date Context Normalizer"
    description = "Normalizes letter O/o to 0 and I/l to 1 in price numbers or dates"

    def apply(self, text: str) -> Tuple[str, bool, List[str]]:
        changes = []
        words = text.split()
        cleaned_words = []
        modified = False

        for word in words:
            # Price pattern e.g., '3.2O' or '3.2o' -> '3.20'
            price_match = re.search(r'(\d+[\.,])([oO\d]{2})\b', word)
            if price_match:
                prefix = price_match.group(1)
                decimals = price_match.group(2).replace('o', '0').replace('O', '0')
                new_word = re.sub(r'(\d+[\.,])[oO\d]{2}\b', f"{prefix}{decimals}", word)
                if new_word != word:
                    changes.append(f"Fixed price decimal '{word}' -> '{new_word}'")
                    word = new_word
                    modified = True

            # Date pattern e.g., '1O.07.2O26' -> '10.07.2026'
            if re.search(r'\d{1,2}[\.,]\d{1,2}[\.,]\d{4}', word.replace('O', '0').replace('o', '0')):
                new_word = word.replace('O', '0').replace('o', '0')
                if new_word != word:
                    changes.append(f"Fixed date digits '{word}' -> '{new_word}'")
                    word = new_word
                    modified = True

            cleaned_words.append(word)

        return " ".join(cleaned_words), modified, changes


class CurrencySymbolRule(PostprocessingRule):
    name = "Currency Symbol Normalizer"
    description = "Fixes letter s or S misread as currency symbol $ before price numbers"

    def apply(self, text: str) -> Tuple[str, bool, List[str]]:
        changes = []
        # Match 's0.00', 'S5.40', 'USDs0.00' where letter s/S precedes digits and decimal
        pattern = r'\b[sS](\d+[\.,]\d{2})\b'

        def replacer(match):
            original = match.group(0)
            amount = match.group(1)
            fixed = f"${amount}"
            changes.append(f"Fixed currency symbol '{original}' -> '{fixed}'")
            return fixed

        new_text = re.sub(pattern, replacer, text)
        return new_text, len(changes) > 0, changes


class TextPostprocessor:
    def __init__(self):
        self.rules: List[PostprocessingRule] = [
            QuantityMultiplierRule(),
            MetricUnitRule(),
            AlphanumericContextRule(),
            CurrencySymbolRule()
        ]

    def process_blocks(self, blocks: List[dict]) -> Tuple[List[dict], dict]:
        """
        Applies all postprocessing rules to layout blocks.
        Updates block["text"] and records block["original_text"] if changed.
        Returns (updated_blocks, stats_summary)
        """
        total_blocks = len(blocks)
        modified_blocks_count = 0
        rule_trigger_counts: Dict[str, int] = {rule.name: 0 for rule in self.rules}
        all_change_logs = []

        for block in blocks:
            original_text = block["text"]
            current_text = original_text
            block_modified = False

            for rule in self.rules:
                new_text, was_modified, changes = rule.apply(current_text)
                if was_modified:
                    current_text = new_text
                    block_modified = True
                    rule_trigger_counts[rule.name] += len(changes)
                    all_change_logs.extend(changes)

            if block_modified:
                modified_blocks_count += 1
                if "original_text" not in block or not block["original_text"]:
                    block["original_text"] = original_text
                block["text"] = current_text
                block["postprocessed"] = True

        stats = {
            "total_blocks": total_blocks,
            "modified_blocks_count": modified_blocks_count,
            "rules_active": len(self.rules),
            "rule_trigger_counts": rule_trigger_counts,
            "change_logs": all_change_logs
        }

        return blocks, stats

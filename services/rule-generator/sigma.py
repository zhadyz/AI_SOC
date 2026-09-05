"""Validated Sigma subset for reproducible backtests on supplied normalized events.

Supported: mapping selectors, value lists, wildcards, contains/startswith/endswith,
all, and boolean conditions with parentheses. Unsupported Sigma features raise;
results are never estimated from keywords or the existence of analyst feedback.
"""

import fnmatch
import re
import yaml


def parse_rule(text):
    if not text or len(text) > 100_000:
        raise ValueError("Rule must contain 1–100000 characters")
    try:
        rule = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError("Invalid YAML") from exc
    if not isinstance(rule, dict) or not isinstance(rule.get("title"), str):
        raise ValueError("A Sigma rule requires a title")
    if not isinstance(rule.get("logsource"), dict) or not rule["logsource"]:
        raise ValueError("A Sigma rule requires a logsource mapping")
    detection = rule.get("detection")
    if not isinstance(detection, dict) or not isinstance(
        detection.get("condition"), str
    ):
        raise ValueError("A Sigma rule requires detection selectors and a condition")
    # Validate the expression and all selectors, even those short-circuited by a match.
    evaluate(rule, {})
    return rule


def _value(actual, expected, modifiers):
    if actual is None or expected is None:
        return actual is expected
    if not isinstance(expected, str):
        return actual == expected
    if not isinstance(actual, str):
        actual = str(actual)
    actual, expected = actual.casefold(), expected.casefold()
    if "contains" in modifiers:
        expected = "*" + expected + "*"
    elif "startswith" in modifiers:
        expected += "*"
    elif "endswith" in modifiers:
        expected = "*" + expected
    return fnmatch.fnmatchcase(actual, expected)


def _selector(selector, event):
    if not isinstance(selector, dict) or not selector:
        raise ValueError(
            "Only nonempty mapping selectors are supported by this backtest backend"
        )
    result = True
    for field, expected in selector.items():
        if not isinstance(field, str) or not field:
            raise ValueError("Selector fields must be nonempty strings")
        if isinstance(expected, dict) or (
            isinstance(expected, list)
            and any(isinstance(v, (dict, list)) for v in expected)
        ):
            raise ValueError("Selector values must be scalars or lists of scalars")
        name, *modifiers = field.split("|")
        if set(modifiers) - {"contains", "startswith", "endswith", "all"}:
            raise ValueError(f"Unsupported Sigma modifier: {field}")
        if sum(m in modifiers for m in ("contains", "startswith", "endswith")) > 1:
            raise ValueError("Combined string modifiers are unsupported")
        actual = event.get(name)
        if name not in event:
            actual = event
            for component in name.split("."):
                actual = actual.get(component) if isinstance(actual, dict) else None
        values = expected if isinstance(expected, list) else [expected]
        if not values:
            raise ValueError("Empty selector values are unsupported")
        matches = [_value(actual, value, modifiers) for value in values]
        result &= all(matches) if "all" in modifiers else any(matches)
    return result


def evaluate(rule, event):
    detection = rule["detection"]
    selectors = {
        name: _selector(value, event)
        for name, value in detection.items()
        if name != "condition"
    }
    expression = detection["condition"]
    tokens = re.findall(r"\(|\)|[A-Za-z_][\w*]*|1", expression)
    if re.sub(r"\s+", "", "".join(tokens)) != re.sub(r"\s+", "", expression):
        raise ValueError("Unsupported Sigma condition syntax")
    position = 0

    def atom():
        nonlocal position
        if position >= len(tokens):
            raise ValueError("Incomplete Sigma condition")
        token = tokens[position]
        position += 1
        if token == "not":
            return not atom()
        if token == "(":
            value = disjunction()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("Unbalanced condition parentheses")
            position += 1
            return value
        if token in {"1", "all"}:
            if position + 1 >= len(tokens) or tokens[position] != "of":
                raise ValueError("Expected 'of' in condition")
            pattern = tokens[position + 1]
            position += 2
            values = [
                value
                for name, value in selectors.items()
                if pattern == "them" or fnmatch.fnmatchcase(name, pattern)
            ]
            if not values:
                raise ValueError("Condition matches no selectors")
            return all(values) if token == "all" else any(values)
        if token not in selectors:
            raise ValueError(f"Unknown condition selector: {token}")
        return selectors[token]

    def conjunction():
        nonlocal position
        value = atom()
        while position < len(tokens) and tokens[position] == "and":
            position += 1
            right = atom()
            value = value and right
        return value

    def disjunction():
        nonlocal position
        value = conjunction()
        while position < len(tokens) and tokens[position] == "or":
            position += 1
            right = conjunction()
            value = value or right
        return value

    result = disjunction()
    if position != len(tokens):
        raise ValueError("Unexpected condition tokens")
    return result


def backtest(text, events):
    rule = parse_rule(text)
    matches = false_positives = benign = labeled = 0
    for item in events:
        match = evaluate(rule, item["event"])
        matches += int(match)
        label = item.get("label")
        labeled += int(label is not None)
        if label == "BENIGN":
            benign += 1
            false_positives += int(match)
    return {
        "status": "evaluated",
        "backend": "documented_sigma_subset",
        "total_tested": len(events),
        "labeled_events": labeled,
        "benign_events": benign,
        "matches": matches,
        "false_positives": false_positives,
        "false_positive_rate": false_positives / benign if benign else None,
    }

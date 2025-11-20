"""
Модуль для сравнения PUML диаграмм с JSON результатами OCR
Адаптирован из kek.py для использования в веб-приложении
"""

import json
import difflib
import re
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from collections import namedtuple

# === Структуры данных ===
ClassInfo = namedtuple("ClassInfo", ["name", "attributes", "methods"])
Relationship = namedtuple(
    "Relationship",
    ["source", "target", "type", "source_label", "target_label", "label"],
)


# === Парсер .puml ===
def parse_puml_file(filepath: str) -> Tuple[Dict[str, ClassInfo], list]:
    """Парсинг PUML файла с извлечением классов, атрибутов и методов"""
    text = Path(filepath).read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("'")
    ]

    classes = {}
    current_class = None

    for line in lines:
        # === ОТКРЫТИЕ КЛАССА ===
        class_match = re.match(
            r'(?:class|abstract|interface|enum)\s+["\']?([A-Za-z_]\w*)["\']?', line
        )
        if class_match:
            name = class_match.group(1)
            current_class = name
            classes[current_class] = {"attributes": [], "methods": []}
            continue

        # === ЗАКРЫТИЕ КЛАССА ===
        if line == "}" and current_class:
            current_class = None
            continue

        # === ВНУТРИ КЛАССА ===
        if current_class:
            # Атрибут: [+-#~]? name : type
            attr_match = re.match(r"([+#~-]?\s*)([^:\s]+)\s*:\s*(.+)", line)
            if attr_match:
                vis = (attr_match.group(1) or "-").strip()
                if not vis:
                    vis = "-"
                name_part = attr_match.group(2).strip()
                type_part = attr_match.group(3).strip()
                classes[current_class]["attributes"].append(
                    f"{vis} {name_part}: {type_part}"
                )
                continue

            # Метод: [+-#~]? name(params) : return_type
            meth_match = re.match(
                r"([+#~-]?\s*)([\w]+)\s*\(([^)]*)\)\s*(?::\s*(.+))?", line
            )
            if meth_match:
                vis = (meth_match.group(1) or "+").strip()
                if not vis:
                    vis = "+"
                name_part = meth_match.group(2)
                params = meth_match.group(3).strip()
                ret = meth_match.group(4).strip() if meth_match.group(4) else "void"
                classes[current_class]["methods"].append(
                    f"{vis} {name_part}({params}): {ret}"
                )
                continue

    # Если классы не описаны блоками — пробуем вытащить из связей
    if not classes:
        all_names = set()
        for line in lines:
            matches = re.findall(r'"?([A-Za-z_]\w*)"?', line)
            all_names.update(matches)
        for name in all_names:
            classes[name] = {"attributes": [], "methods": []}

    class_dict = {
        name: ClassInfo(name, data["attributes"], data["methods"])
        for name, data in classes.items()
    }
    return class_dict, []


# === Нормализация атрибута ===
def normalize_attribute(attr: str) -> str:
    """Нормализует атрибут, добавляя видимость если её нет"""
    attr = attr.strip()
    visibility = "-"
    if attr and attr[0] in "+-#~":
        visibility = attr[0]
        attr = attr[1:].strip()

    if ":" in attr:
        name_part, type_part = attr.split(":", 1)
        return f"{visibility} {name_part.strip()}: {type_part.strip()}"
    return f"{visibility} {attr}"


# === Парсер JSON от детектора ===
def parse_json_diagram(filepath: str) -> Tuple[Dict[str, ClassInfo], list]:
    """Парсинг JSON файла с результатами OCR"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    classes = {}

    for entity in data.get("entities", []):
        name = entity["name"].strip()

        # Атрибуты
        attributes = []
        for raw in entity.get("attributes", []):
            attributes.append(normalize_attribute(raw))

        # Методы
        methods = []
        for raw in entity.get("methods", []):
            meth = raw.strip()

            # Если видимость уже есть — оставляем
            if meth and meth[0] in "+-#~":
                cleaned = meth
            else:
                # Чистим пробелы в сигнатуре
                meth = re.sub(r"\s*:\s*", ": ", meth)
                meth = re.sub(r"\s*\(\s*", "(", meth)
                meth = re.sub(r"\s*\)\s*", ")", meth)
                # Если есть возвращаемый тип
                if ": " in meth[1:]:  # не с первого символа
                    parts = meth.split(": ", 1)
                    meth = f"{parts[0]}: {parts[1]}"
                cleaned = "+ " + meth

            methods.append(cleaned)

        classes[name] = ClassInfo(name, attributes, methods)

    return classes, []


# === Основная функция сравнения: .puml (эталон) vs .json (студент) ===
def _match_attributes(
    etalon_attrs: List[str],
    student_attrs: List[str],
    threshold: float,
) -> Tuple[int, List[str], List[str]]:
    """Match attribute lists using a greedy fuzzy comparison."""
    matched_etalon = set()
    matched_student = set()
    for s_idx, student_attr in enumerate(student_attrs):
        best_idx = None
        best_ratio = 0.0
        for e_idx, etalon_attr in enumerate(etalon_attrs):
            if e_idx in matched_etalon:
                continue
            ratio = difflib.SequenceMatcher(None, etalon_attr, student_attr).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = e_idx
        if best_idx is not None and best_ratio >= threshold:
            matched_etalon.add(best_idx)
            matched_student.add(s_idx)

    missing = [
        attr for idx, attr in enumerate(etalon_attrs) if idx not in matched_etalon
    ]
    extra = [
        attr for idx, attr in enumerate(student_attrs) if idx not in matched_student
    ]
    return len(matched_etalon), missing, extra


def compare_puml_with_json(
    etalon_puml_path: str,
    student_json_path: str,
    class_threshold: float = 0.90,
    attr_threshold: float = 0.85,
) -> Dict:
    """
    Сравнивает PUML эталон с JSON результатом
    Возвращает словарь с результатами сравнения
    """
    etalon_classes, _ = parse_puml_file(etalon_puml_path)
    student_classes, _ = parse_json_diagram(student_json_path)

    if not etalon_classes:
        return {"error": "Эталон пустой — нельзя сравнить", "similarity": 1.0}

    # Приводим имена к нижнему регистру для сравнения
    etalon_low = {c.name.lower(): c for c in etalon_classes.values()}
    student_low = {c.name.lower(): c for c in student_classes.values()}

    # === 1. Сравнение классов ===
    matched_classes = 0
    class_mapping: Dict[str, Dict[str, Optional[float]]] = {}
    matched_student_lows = set()

    for e_low, e_cls in etalon_low.items():
        best_ratio = 0
        best_student_low = None
        for s_low, s_cls in student_low.items():
            ratio = difflib.SequenceMatcher(None, e_low, s_low).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_student_low = s_low
        if best_ratio >= class_threshold:
            matched_classes += 1
            class_mapping[e_low] = {"student": best_student_low, "ratio": best_ratio}
            matched_student_lows.add(best_student_low)

    precision_c = matched_classes / len(student_classes) if student_classes else 0
    recall_c = matched_classes / len(etalon_classes)
    f1_classes = (
        2 * precision_c * recall_c / (precision_c + recall_c)
        if (precision_c + recall_c) > 0
        else 0
    )

    # === 2. Сравнение атрибутов ===
    etalon_attr_count = 0
    student_attr_count = 0
    matched_attrs = 0
    attribute_diffs = []

    for e_low, e_cls in etalon_low.items():
        normalized_etalon_attrs = [
            normalize_attribute(attr) for attr in e_cls.attributes
        ]
        etalon_attr_count += len(normalized_etalon_attrs)
        mapping = class_mapping.get(e_low)

        if mapping and mapping["student"] is not None:
            s_low = mapping["student"]
            s_cls = student_low[s_low]
            normalized_student_attrs = [
                normalize_attribute(attr) for attr in s_cls.attributes
            ]
            student_attr_count += len(normalized_student_attrs)

            matches, missing_attrs, extra_attrs = _match_attributes(
                normalized_etalon_attrs, normalized_student_attrs, attr_threshold
            )
            matched_attrs += matches
            if missing_attrs or extra_attrs:
                attribute_diffs.append(
                    {
                        "etalon_class": e_cls.name,
                        "student_class": s_cls.name,
                        "missing": missing_attrs,
                        "extra": extra_attrs,
                    }
                )
        else:
            if normalized_etalon_attrs:
                attribute_diffs.append(
                    {
                        "etalon_class": e_cls.name,
                        "student_class": None,
                        "missing": normalized_etalon_attrs,
                        "extra": [],
                    }
                )

    for s_low, s_cls in student_low.items():
        if s_low in matched_student_lows:
            continue
        normalized_student_attrs = [
            normalize_attribute(attr) for attr in s_cls.attributes
        ]
        if normalized_student_attrs:
            attribute_diffs.append(
                {
                    "etalon_class": None,
                    "student_class": s_cls.name,
                    "missing": [],
                    "extra": normalized_student_attrs,
                }
            )

    no_attributes = etalon_attr_count == 0 and student_attr_count == 0

    if no_attributes:
        # No attributes on either side – don't penalize the overall score
        precision_a = recall_a = f1_attrs = 1.0
    else:
        precision_a = matched_attrs / student_attr_count if student_attr_count else 0
        recall_a = matched_attrs / etalon_attr_count if etalon_attr_count else 0
        f1_attrs = (
            2 * precision_a * recall_a / (precision_a + recall_a)
            if (precision_a + recall_a) > 0
            else 0
        )

    # === Итоговая схожесть ===
    total_similarity = 0.6 * f1_classes + 0.4 * f1_attrs

    return {
        "similarity": total_similarity,
        "score": total_similarity * 100,
        "classes": {
            "f1": f1_classes,
            "precision": precision_c,
            "recall": recall_c,
            "etalon_count": len(etalon_classes),
            "student_count": len(student_classes),
            "matched": matched_classes,
        },
        "attributes": {
            "f1": f1_attrs,
            "precision": precision_a,
            "recall": recall_a,
            "etalon_count": etalon_attr_count,
            "student_count": student_attr_count,
            "matched": matched_attrs,
        },
        "diff": {
            "classes": {
                "missing": [
                    etalon_low[e_low].name
                    for e_low in etalon_low
                    if e_low not in class_mapping
                ],
                "extra": [
                    student_low[s_low].name
                    for s_low in student_low
                    if s_low not in matched_student_lows
                ],
            },
            "attributes": attribute_diffs,
        },
    }


def compare_batch(etalon_files: List[str], student_files: List[str]) -> List[Dict]:
    """
    Массовое сравнение файлов
    Возвращает список результатов для каждой пары
    """
    results = []

    for etalon_path in etalon_files:
        etalon_name = Path(etalon_path).stem

        # Ищем соответствующий JSON файл
        matched_student = None
        for student_path in student_files:
            student_name = Path(student_path).stem
            # Пробуем найти совпадение по имени
            if (
                etalon_name.lower() in student_name.lower()
                or student_name.lower() in etalon_name.lower()
            ):
                matched_student = student_path
                break

        if matched_student:
            result = compare_puml_with_json(etalon_path, matched_student)
            result["etalon_file"] = Path(etalon_path).name
            result["student_file"] = Path(matched_student).name
            results.append(result)
        else:
            results.append(
                {
                    "etalon_file": Path(etalon_path).name,
                    "student_file": "Не найден",
                    "error": "Соответствующий JSON файл не найден",
                    "similarity": 0.0,
                    "score": 0.0,
                }
            )

    return results

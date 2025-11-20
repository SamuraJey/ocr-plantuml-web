import json
import difflib
import re
import os
from pathlib import Path
from typing import Dict, Tuple
from collections import namedtuple

# === Структуры данных ===
ClassInfo = namedtuple("ClassInfo", ["name", "attributes", "methods"])
Relationship = namedtuple("Relationship", ["source", "target", "type", "source_label", "target_label", "label"])

# === Парсер .puml (твой, но чуть почищен) ===
def parse_puml_file(filepath: str) -> Tuple[Dict[str, ClassInfo], list]:
    text = Path(filepath).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith("'")]

    classes = {}
    current_class = None

    for line in lines:

        # === ОТКРЫТИЕ КЛАССА ===
        class_match = re.match(r'(?:class|abstract|interface|enum)\s+["\']?([A-Za-z_]\w*)["\']?', line)
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
            attr_match = re.match(r'([+#~-]?\s*)([^:\s]+)\s*:\s*(.+)', line)
            if attr_match:
                vis = (attr_match.group(1) or "-").strip()
                if not vis:
                    vis = "-"
                name_part = attr_match.group(2).strip()
                type_part = attr_match.group(3).strip()
                classes[current_class]["attributes"].append(f"{vis} {name_part}: {type_part}")
                continue

            # Метод: [+-#~]? name(params) : return_type
            meth_match = re.match(r'([+#~-]?\s*)([\w]+)\s*\(([^)]*)\)\s*(?::\s*(.+))?', line)
            if meth_match:
                vis = (meth_match.group(1) or "+").strip()
                if not vis:
                    vis = "+"
                name_part = meth_match.group(2)
                params = meth_match.group(3).strip()
                ret = meth_match.group(4).strip() if meth_match.group(4) else "void"
                classes[current_class]["methods"].append(f"{vis} {name_part}({params}): {ret}")
                continue

        # === СВЯЗИ — ИГНОРИРУЕМ ВСЁ, ЧТО НЕ КЛАССЫ ===
        # Никаких re.match для стрелок! Полностью убираем риск ошибки

    # Если классы не описаны блоками — пробуем вытащить из связей (на всякий случай)
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
    return class_dict, []  # связи не возвращаем вообще
# === Нормализация атрибута ===
def normalize_attribute(attr: str) -> str:
    attr = attr.strip()
    visibility = "-"
    if attr and attr[0] in "+-#~":
        visibility = attr[0]
        attr = attr[1:].strip()

    if ":" in attr:
        name_part, type_part = attr.split(":", 1)
        return f"{visibility} {name_part.strip()}: {type_part.strip()}"
    return f"{visibility} {attr}"


# === Парсер JSON от детектора (твой формат) ===
def parse_json_diagram(filepath: str) -> Tuple[Dict[str, ClassInfo], list]:
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
                meth = re.sub(r'\s*:\s*', ': ', meth)
                meth = re.sub(r'\s*\(\s*', '(', meth)
                meth = re.sub(r'\s*\)\s*', ')', meth)
                # Если есть возвращаемый тип
                if ": " in meth[1:]:  # не с первого символа
                    parts = meth.split(": ", 1)
                    meth = f"{parts[0]}: {parts[1]}"
                cleaned = "+ " + meth

            methods.append(cleaned)

        classes[name] = ClassInfo(name, attributes, methods)

    return classes, []  # связей нет


# === Основная функция сравнения: .puml (эталон) vs .json (студент) ===
def compare_puml_with_json(
    etalon_puml_path: str,
    student_json_path: str,
    class_threshold: float = 0.90,
    attr_threshold: float = 0.85
) -> Tuple[float, str]:
    etalon_classes, _ = parse_puml_file(etalon_puml_path)
    student_classes, _ = parse_json_diagram(student_json_path)

    if not etalon_classes:
        return 1.0, "Эталон пустой — нельзя сравнить"

    # Приводим имена к нижнему регистру для сравнения
    etalon_low = {c.name.lower(): c for c in etalon_classes.values()}
    student_low = {c.name.lower(): c for c in student_classes.values()}

    # === 1. Сравнение классов ===
    matched_classes = 0
    class_mapping = {}  # эталон_low → студент_name

    for e_low, e_cls in etalon_low.items():
        best_ratio = 0
        best_student_name = None
        for s_low, s_cls in student_low.items():
            ratio = difflib.SequenceMatcher(None, e_low, s_low).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_student_name = s_cls.name
        if best_ratio >= class_threshold:
            matched_classes += 1
            class_mapping[e_low] = best_student_name

    precision_c = matched_classes / len(student_classes) if student_classes else 0
    recall_c = matched_classes / len(etalon_classes)
    f1_classes = 2 * precision_c * recall_c / (precision_c + recall_c) if (precision_c + recall_c) > 0 else 0

    # === 2. Сравнение атрибутов ===
    etalon_attrs = set()
    for cls in etalon_classes.values():
        for attr in cls.attributes:
            norm = normalize_attribute(attr)
            etalon_attrs.add(f"{cls.name.lower()}::{norm}")

    student_attrs = set()
    matched_attrs = 0

    for s_cls in student_classes.values():
        s_low = s_cls.name.lower()
        # Ищем, какой эталонный класс соответствует
        matched_etalon_low = None
        for e_low in etalon_low:
            if difflib.SequenceMatcher(None, e_low, s_low).ratio() >= class_threshold:
                matched_etalon_low = e_low
                break

        if matched_etalon_low:
            for attr in s_cls.attributes:
                norm = normalize_attribute(attr)
                key = f"{s_low}::{norm}"
                student_attrs.add(key)

                # Проверяем, есть ли такой же в эталоне
                for e_key in etalon_attrs:
                    e_cls_low, e_norm = e_key.split("::", 1)
                    if e_cls_low == matched_etalon_low:
                        if difflib.SequenceMatcher(None, e_norm, norm).ratio() >= attr_threshold:
                            matched_attrs += 1
                            break

    precision_a = matched_attrs / len(student_attrs) if student_attrs else 0
    recall_a = matched_attrs / len(etalon_attrs) if etalon_attrs else 0
    f1_attrs = 2 * precision_a * recall_a / (precision_a + recall_a) if (precision_a + recall_a) > 0 else 0

    # === Итоговая схожесть (без связей) ===
    total_similarity = 0.6 * f1_classes + 0.4 * f1_attrs  # 60% классы, 40% атрибуты

    filename = os.path.basename(student_json_path)
    report = f"""
{60*'='}
Файл: {filename}
{60*'='}
Классы     F1 = {f1_classes:.3f}   (P={precision_c:.3f}, R={recall_c:.3f})
Атрибуты   F1 = {f1_attrs:.3f}   (P={precision_a:.3f}, R={recall_a:.3f})
{60*'='}
Общая схожесть: {total_similarity:.1%}
Оценка: {total_similarity * 100:.1f}/100
{60*'='}
""".strip()

    return total_similarity, report


# === Пример использования ===
if __name__ == "__main__":
    score, text = compare_puml_with_json(
        etalon_puml_path="4_2.puml",
        student_json_path="line_detection_4_2.json"
    )
    print(text)
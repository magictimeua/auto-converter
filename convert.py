import os
import requests
import xml.etree.ElementTree as ET

def download_file(url, dest_path):
    response = requests.get(url)
    response.raise_for_status()
    with open(dest_path, 'wb') as f:
        f.write(response.content)
    print(f"Файл завантажено і збережено у {dest_path}")

def convert_categories_and_hierarchy(
    input_file,
    output_file,
    category_mappings,
    custom_categories
):
    tree = ET.parse(input_file)
    root = tree.getroot()
    categories_element = root.find(".//categories")

    # Додаємо нові кастомні категорії
    for cat in custom_categories:
        new_cat = ET.Element('category', id=cat["id"])
        new_cat.text = cat["name"]
        categories_element.insert(0, new_cat)

    # Прив’язуємо дочірні категорії до відповідних parentId
    for category in categories_element.findall("category"):
        cat_id = category.attrib["id"]
        for parent_cat in custom_categories:
            if cat_id in parent_cat["child_ids"]:
                category.set("parentId", parent_cat["id"])

    # Заміна назв категорій у секції categories
    for old_name, new_name in category_mappings:
        for category in categories_element.findall("category"):
            if category.text == old_name:
                category.text = new_name

    # Заміна categoryId у товарах
    for offer in root.find(".//offers").findall("offer"):
        category_id = offer.find("categoryId").text
        category_element = root.find(f".//category[@id='{category_id}']")
        if category_element is not None:
            for old_name, new_name in category_mappings:
                if category_element.text == old_name:
                    new_cat_el = root.find(f".//category[.='{new_name}']")
                    if new_cat_el is not None:
                        offer.find("categoryId").text = new_cat_el.attrib["id"]

    # Заміна <name> на <name_ua> і <description> на <description_ua>
    for offer in root.find(".//offers").findall("offer"):
        name_el = offer.find("name")
        if name_el is not None:
            name_ua_el = ET.Element("name_ua")
            name_ua_el.text = name_el.text
            offer.remove(name_el)
            offer.append(name_ua_el)

        desc_el = offer.find("description")
        if desc_el is not None:
            desc_ua_el = ET.Element("description_ua")
            desc_ua_el.text = desc_el.text
            offer.remove(desc_el)
            offer.append(desc_ua_el)

    # Форматування
    def indent(elem, level=0):
        i = "\n" + level * "    "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            for child in elem:
                indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

    indent(root)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    category_mappings = [
        ('Вібратори до 15см', 'Компактні'),
        ('Вібратори від 15см', 'Довгі')
    ]

    custom_categories = [
        {
            "id": "999",
            "name": "Секс-іграшки",
            "child_ids": {"11", "12", "13", "33", "28", "34", "50", "35", "70", "82"}
        },
        {
            "id": "998",
            "name": "Прелюдія",
            "child_ids": {"79", "39", "101", "40"}
        },
        {
            "id": "997",
            "name": "Сексуальне здоров’я",
            "child_ids": {"129", "124", "96"}
        },
        {
            "id": "996",
            "name": "Різне",
            "child_ids": {"83", "78", "139", "168", "169"}
        }
    ]

    input_file = "shop.yml"
    output_file = "converted.yml"

    url = "https://blissclub.com.ua/user/downloadyml?hash=c5f296cdb87c9780b8d77379aaacf981&filename=products_with_html_breaks_retail.yml"

    download_file(url, input_file)

    convert_categories_and_hierarchy(
        input_file,
        output_file,
        category_mappings,
        custom_categories
    )

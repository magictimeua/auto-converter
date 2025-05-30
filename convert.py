import os
import requests
import xml.etree.ElementTree as ET
import time

ENABLE_DESCRIPTION_GENERATION = False

if ENABLE_DESCRIPTION_GENERATION:
    from openai import OpenAI
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        raise RuntimeError("Встановіть змінну середовища OPENAI_API_KEY для генерації описів")
    client = OpenAI(api_key=openai_api_key)

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
    custom_categories,
    portal_id_mappings
):
    tree = ET.parse(input_file)
    root = tree.getroot()
    categories_element = root.find(".//categories")

    # Додаємо нові кастомні категорії спереду
    for cat in custom_categories:
        new_cat = ET.Element('category', id=cat["id"])
        new_cat.text = cat["name"]
        categories_element.insert(0, new_cat)

    # Прив’язуємо дочірні категорії до parentId
    for category in categories_element.findall("category"):
        cat_id = category.attrib.get("id", "")
        for parent_cat in custom_categories:
            if cat_id in parent_cat["child_ids"]:
                category.set("parentId", parent_cat["id"])

    # Заміна назв категорій у секції categories
    for old_name, new_name in category_mappings:
        for category in categories_element.findall("category"):
            if category.text and category.text == old_name:
                category.text = new_name

    # Заміна categoryId у товарах
    for offer in root.find(".//offers").findall("offer"):
        category_id = offer.find("categoryId").text
        category_element = root.find(f".//category[@id='{category_id}']")
        if category_element is not None:
            for old_name, new_name in category_mappings:
                if category_element.text == old_name:
                    # Знайти категорію з новим ім’ям
                    new_cat_el = None
                    for c in categories_element.findall("category"):
                        if c.text == new_name:
                            new_cat_el = c
                            break
                    if new_cat_el is not None:
                        offer.find("categoryId").text = new_cat_el.attrib["id"]

    # Додаємо portal_id після parentId (якщо є), інакше після id
    for category in categories_element.findall("category"):
        cat_id = category.attrib.get("id", "")
        if cat_id in portal_id_mappings:
            portal_id_value = portal_id_mappings[cat_id]
            # Відновлюємо атрибути з правильним порядком
            attribs = category.attrib.copy()
            attribs["portal_id"] = portal_id_value
            # Атрибут order: id -> parentId (якщо є) -> portal_id
            new_attribs = {}
            new_attribs["id"] = attribs.pop("id")
            if "parentId" in attribs:
                new_attribs["parentId"] = attribs.pop("parentId")
            new_attribs["portal_id"] = attribs.pop("portal_id")
            # Додаємо інші атрибути, якщо є
            for k, v in attribs.items():
                new_attribs[k] = v
            category.attrib.clear()
            category.attrib.update(new_attribs)

    # Заміна тегів name та description на name_ua і description_ua
    for offer in root.find(".//offers").findall("offer"):
        name_el = offer.find("name")
        if name_el is not None:
            # Копіюємо текст name у name_ua, але залишаємо name
            name_ua_el = ET.Element("name_ua")
            name_ua_el.text = name_el.text
            offer.append(name_ua_el)
    
        desc_el = offer.find("description")
        if desc_el is not None:
            desc_ua_el = ET.Element("description_ua")
            desc_ua_el.text = desc_el.text
            offer.append(desc_ua_el)

    if ENABLE_DESCRIPTION_GENERATION:
        max_test_items = 5
        count = 0
        offers = root.find(".//offers").findall("offer")
        for offer in offers:
            if count >= max_test_items:
                break
            name_el = offer.find("name_ua")
            desc_el = offer.find("description_ua")
            if name_el is not None and desc_el is not None:
                product_name = name_el.text or ""
                current_description = desc_el.text or ""
                print(f"Генеруємо опис для: {product_name}")
                new_description = generate_description(product_name, current_description)
                desc_el.text = new_description
                count += 1
                time.sleep(2)

    # Функція для гарного форматування XML
    def indent(elem, level=0):
        i = "\n" + level*"    "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            for child in elem:
                indent(child, level+1)
                if not child.tail or not child.tail.strip():
                    child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    indent(root)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)

def generate_description(product_name, current_description):
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant who writes SEO-optimized product descriptions in Ukrainian."
            },
            {
                "role": "user",
                "content": (
                    f"Напиши унікальний, грамотний і SEO-оптимізований опис українською мовою "
                    f"для товару: {product_name}. "
                    f"Поточний опис: {current_description}. "
                    f"Опис має бути природнім, інформативним і без зайвої води."
                )
            }
        ]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Помилка генерації опису для {product_name}: {e}")
        return current_description


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

    portal_id_mappings = {
        "996": "1767",
        "78": "161007",
        "139": "410201",
        "168": "3504",
        "169": "5280501",
        "129": "161008",
        "124": "15131001",
        "96": "16131201",
        "79": "161610",
        "39": "161002",
        "101": "161002",
        "40": "161002",
        "999": "161001",
        "38": "161003",
        "63": "161007",
        "58": "351",
        "59": "31202",
        "60": "16100403",
        "62": "304",
        "68": "3121101",
        "127": "3390107",
        "69": "16100403",
        "72": "319",
        "73": "31208",
        "74": "31206",
        "75": "324",
        "76": "16100404",
        "77": "35402",
        "83": "1767",
        "88": "1767",
        "89": "1767",
        "90": "1767",
        "91": "1767",
        "92": "1767",
        "93": "1767",
        "97": "1767",
        "98": "1767",
        "100": "1767",
        "165": "1767",
        "80": "161610",
        "81": "161610",
        "41": "161002",
        "42": "161002",
        "43": "161002",
        "44": "161002",
        "128": "161002",
        "11": "161001",
        "12": "161001",
        "82": "161001",
        "13": "161001",
        "33": "161001",
        "28": "161001",
        "34": "161001",
        "50": "161001",
        "35": "161001",
        "14": "161001",
        "102": "161001",
        "143": "161001",
        "18": "161001",
        "19": "161001",
        "27": "161001",
        "21": "161001",
        "107": "161001",
        "123": "161001",
        "131": "161001",
        "144": "161001",
        "145": "161001",
        "23": "161001",
        "22": "161001",
        "24": "161001",
        "146": "161001",
        "26": "161001",
        "120": "161001",
        "31": "161001",
        "150": "161001",
        "32": "161001",
        "161": "161001",
        "84": "161001",
        "147": "161001",
        "148": "161001",
        "149": "161001",
        "151": "161001",
        "142": "161001",
        "141": "161001",
        "29": "161001",
        "30": "161001",
        "71": "161001",
        "54": "161001",
        "55": "161001",
        "153": "161001",
        "152": "161001",
        "122": "161001",
        "52": "161001",
        "51": "161001",
        "53": "161001",
        "156": "161001",
        "130": "161001",
        "110": "161001",
        "36": "161001",
        "164": "161001",
        "163": "161001",
        "37": "161001",
        "45": "161001",
        "109": "161001",
        "70": "161001",
        "46": "161007",
        "158": "161007",
        "159": "161007",
        "48": "161007",
        "167": "161007",
        "49": "161007",
        "138": "161007",
        "166": "161007",
        "137": "161007",
        "104": "161007",
        "66": "161007",
        "126": "161007",
        "64": "161007",
        "65": "161007",
        "67": "161007",
        "136": "161007",
        "85": "161007",
        "86": "161007",
        "95": "161007",
        "105": "161007",
        "106": "161007",
        "112": "161007",
        "121": "161007",
        "114": "161007",
        "115": "161007",
        "116": "161007",
        "117": "161007",
        "118": "161007",
        "119": "161007",
        "132": "161007"

    }

    input_file = "shop.yml"
    output_file = "converted.yml"

    url = "https://blissclub.com.ua/user/downloadyml?hash=c5f296cdb87c9780b8d77379aaacf981&filename=products_with_html_breaks_retail.yml"

    download_file(url, input_file)

    convert_categories_and_hierarchy(
        input_file,
        output_file,
        category_mappings,
        custom_categories,
        portal_id_mappings
    )

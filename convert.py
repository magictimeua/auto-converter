import os
import requests
import xml.etree.ElementTree as ET
import time

ENABLE_DESCRIPTION_GENERATION = False

if ENABLE_DESCRIPTION_GENERATION:
    from openai import OpenAI
    openai_api_key = os.getenv('OPENAI_API_KEY')
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
):
    tree = ET.parse(input_file)
    root = tree.getroot()
    categories_element = root.find(".//categories")

    # Відповідність id категорій нашого файлу до portal_id Prom.ua
    portal_id_map = {
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
    }

    # Додаємо portal_id до тегів <category> якщо id в нашому списку
    for category in categories_element.findall("category"):
        cat_id = category.attrib.get("id")
        if cat_id in portal_id_map:
            category.set("portal_id", portal_id_map[cat_id])

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

    # Додаємо name_ua та description_ua, залишаючи name і description
    for offer in root.find(".//offers").findall("offer"):
        name_el = offer.find("name")
        if name_el is not None:
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

    input_file = "shop.yml"
    output_file = "converted.yml"

    url = "https://blissclub.com.ua/user/downloadyml?hash=c5f296cdb87c9780b8d77379aaacf981&filename=products_with_html_breaks_retail.yml"

    download_file(url, input_file)

    convert_categories_and_hierarchy(
        input_file,
        output_file,
        category_mappings,
    )

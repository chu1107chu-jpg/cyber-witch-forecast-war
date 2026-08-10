"""
Страница «Политики: Битва» — Cyberpunk × Kawaii Edition
Выбери бойцов · Назначь 3 атаки · Поставь монеты · Сразись!
"""
import streamlit as st
import random

# ──────────────────────────────────────────────────────────────
#  ХАРАКТЕРИСТИКИ
# ──────────────────────────────────────────────────────────────
STAT_LABELS = {
    "strength":  "💪 Сила",
    "cunning":   ":material/psychology: Хитрость",
    "charisma":  "✨ Харизма",
    "resources": ":material/payments: Ресурсы",
    "luck":      "🍀 Удача",
    "madness":   "🤪 Безумие",
}

ATTACK_TYPE_LABELS = {
    "military":    ":material/swords: Военная",
    "economic":    ":material/payments: Экономическая",
    "diplomatic":  "🤝 Дипломатия",
    "media":       "📺 Медийная",
    "intrigue":    "🕵️ Интрига",
    "provocation": "🎭 Провокация",
}

CATEGORIES = ["🇷🇺 Россия", "🇺🇸 США", "🇺🇦 Украина", ":material/public: Мир", ":material/swords: Легенды"]

# ──────────────────────────────────────────────────────────────
#  30 ПОЛИТИКОВ
# ──────────────────────────────────────────────────────────────
POLITICIANS = [
    # ═══════════════ 🇷🇺 РОССИЯ (8) ═══════════════
    {"id": "putin", "name": "Владимир Путин", "icon": "🐻", "category": "🇷🇺 Россия",
     "era": "1999–н.в.", "desc": "Тот самый. Многоходовочка — его второе имя.",
     "stats": {"strength": 7, "cunning": 10, "charisma": 8, "resources": 10, "luck": 8, "madness": 6},
     "attacks": [
         {"name": "Многоходовочка", "type": "intrigue", "power": 95},
         {"name": "Ядерный чемоданчик", "type": "military", "power": 100},
         {"name": "Газовый вентиль", "type": "economic", "power": 88},
         {"name": "Прямая линия", "type": "media", "power": 75},
         {"name": "Дзюдо-бросок", "type": "military", "power": 70},
         {"name": "Взгляд КГБ", "type": "intrigue", "power": 82},
     ]},
    {"id": "stalin", "name": "Иосиф Сталин", "icon": "⭐", "category": "🇷🇺 Россия",
     "era": "1924–1953", "desc": "Усатый вождь народов. Пятилетку — за три года.",
     "stats": {"strength": 9, "cunning": 9, "charisma": 7, "resources": 8, "luck": 5, "madness": 10},
     "attacks": [
         {"name": "Расстрельный список", "type": "intrigue", "power": 98},
         {"name": "ГУЛАГ", "type": "military", "power": 95},
         {"name": "Усы гнева", "type": "provocation", "power": 65},
         {"name": "Индустриализация", "type": "economic", "power": 85},
         {"name": "Красная армия", "type": "military", "power": 90},
         {"name": "Враг народа", "type": "media", "power": 80},
     ]},
    {"id": "lenin", "name": "Владимир Ленин", "icon": ":red[:material/circle:]", "category": "🇷🇺 Россия",
     "era": "1917–1924", "desc": "Живее всех живых. Мировая революция и лампочка Ильича.",
     "stats": {"strength": 5, "cunning": 9, "charisma": 10, "resources": 6, "luck": 7, "madness": 9},
     "attacks": [
         {"name": "Искра революции", "type": "media", "power": 92},
         {"name": "Экспроприация", "type": "economic", "power": 88},
         {"name": "Залп Авроры", "type": "military", "power": 95},
         {"name": "Агитплакат", "type": "media", "power": 78},
         {"name": "Декрет о земле", "type": "diplomatic", "power": 82},
         {"name": "Пломбированный вагон", "type": "intrigue", "power": 75},
     ]},
    {"id": "peter1", "name": "Пётр I Великий", "icon": "⚓", "category": "🇷🇺 Россия",
     "era": "1682–1725", "desc": "Прорубил окно в Европу. Ростом 2 метра, нравом — кипяток.",
     "stats": {"strength": 10, "cunning": 7, "charisma": 9, "resources": 8, "luck": 6, "madness": 8},
     "attacks": [
         {"name": "Прорубить окно", "type": "military", "power": 90},
         {"name": "Бритьё бород", "type": "provocation", "power": 65},
         {"name": "Строительство флота", "type": "military", "power": 88},
         {"name": "Великое посольство", "type": "diplomatic", "power": 80},
         {"name": "Палка-трость", "type": "military", "power": 72},
         {"name": "Европеизация", "type": "economic", "power": 78},
     ]},
    {"id": "gorbachev", "name": "Михаил Горбачёв", "icon": "🍕", "category": "🇷🇺 Россия",
     "era": "1985–1991", "desc": "Перестроил так, что всё сломалось. Зато реклама Pizza Hut.",
     "stats": {"strength": 3, "cunning": 6, "charisma": 9, "resources": 4, "luck": 3, "madness": 4},
     "attacks": [
         {"name": "Перестройка", "type": "diplomatic", "power": 70},
         {"name": "Гласность", "type": "media", "power": 65},
         {"name": "Реклама Pizza Hut", "type": "media", "power": 50},
         {"name": "Пятно на лбу", "type": "provocation", "power": 40},
         {"name": "Ускорение", "type": "economic", "power": 55},
         {"name": "Разрядка", "type": "diplomatic", "power": 60},
     ]},
    {"id": "yeltsin", "name": "Борис Ельцин", "icon": "🍾", "category": "🇷🇺 Россия",
     "era": "1991–1999", "desc": "Дирижировал оркестром, танцевал на сцене, управлял страной. Иногда одновременно.",
     "stats": {"strength": 6, "cunning": 5, "charisma": 7, "resources": 5, "luck": 7, "madness": 8},
     "attacks": [
         {"name": "Танцы на сцене", "type": "provocation", "power": 60},
         {"name": "Загогулина", "type": "intrigue", "power": 65},
         {"name": "Расстрел Белого дома", "type": "military", "power": 85},
         {"name": "Я устал, я ухожу", "type": "provocation", "power": 70},
         {"name": "Дирижирование оркестром", "type": "media", "power": 55},
         {"name": "Танк на мосту", "type": "military", "power": 80},
     ]},
    {"id": "catherine2", "name": "Екатерина II Великая", "icon": "👑", "category": "🇷🇺 Россия",
     "era": "1762–1796", "desc": "Немка, которая стала самой русской императрицей. Золотой век и фавориты.",
     "stats": {"strength": 6, "cunning": 9, "charisma": 10, "resources": 9, "luck": 8, "madness": 5},
     "attacks": [
         {"name": "Потёмкинские деревни", "type": "intrigue", "power": 85},
         {"name": "Золотой век", "type": "economic", "power": 90},
         {"name": "Присоединение Крыма", "type": "military", "power": 88},
         {"name": "Придворная интрига", "type": "intrigue", "power": 82},
         {"name": "Письмо Вольтеру", "type": "diplomatic", "power": 70},
         {"name": "Фавориты", "type": "provocation", "power": 75},
     ]},
    {"id": "ivan4", "name": "Иван Грозный", "icon": "👿", "category": "🇷🇺 Россия",
     "era": "1547–1584", "desc": "Первый царь. Убил сына, разгромил Новгород, написал оперу... ой, нет, не оперу.",
     "stats": {"strength": 8, "cunning": 8, "charisma": 6, "resources": 7, "luck": 4, "madness": 10},
     "attacks": [
         {"name": "Опричнина", "type": "military", "power": 95},
         {"name": "Посох гнева", "type": "military", "power": 88},
         {"name": "Взятие Казани", "type": "military", "power": 90},
         {"name": "Библиотека Грозного", "type": "intrigue", "power": 65},
         {"name": "Царский гнев", "type": "provocation", "power": 85},
         {"name": "Переписка с Курбским", "type": "media", "power": 60},
     ]},

    # ═══════════════ 🇺🇸 США (7) ═══════════════
    {"id": "biden", "name": "Джо Байден", "icon": "😴", "category": "🇺🇸 США",
     "era": "2021–2025", "desc": "Сонный Джо. Спотыкается, но санкции вводит чётко.",
     "stats": {"strength": 3, "cunning": 5, "charisma": 6, "resources": 9, "luck": 5, "madness": 4},
     "attacks": [
         {"name": "Спотыкание на трапе", "type": "provocation", "power": 45},
         {"name": "Забыл что сказал", "type": "provocation", "power": 35},
         {"name": "Пакет санкций", "type": "economic", "power": 82},
         {"name": "Мороженое-дипломатия", "type": "diplomatic", "power": 50},
         {"name": "Военная помощь", "type": "military", "power": 75},
         {"name": "Тёмные очки", "type": "media", "power": 55},
     ]},
    {"id": "trump", "name": "Дональд Трамп", "icon": "🍊", "category": "🇺🇸 США",
     "era": "2017–2021, 2025–", "desc": "Оранжевый гений. Make America Great Again. Снова. И снова.",
     "stats": {"strength": 5, "cunning": 7, "charisma": 10, "resources": 10, "luck": 9, "madness": 9},
     "attacks": [
         {"name": "Построю стену!", "type": "military", "power": 85},
         {"name": "Ты уволен!", "type": "economic", "power": 90},
         {"name": "Твит ярости", "type": "media", "power": 88},
         {"name": "Сделка века", "type": "diplomatic", "power": 80},
         {"name": "Оранжевый загар", "type": "provocation", "power": 60},
         {"name": "MAGA-митинг", "type": "media", "power": 82},
     ]},
    {"id": "obama", "name": "Барак Обама", "icon": "🏀", "category": "🇺🇸 США",
     "era": "2009–2017", "desc": "Yes We Can. Нобелевка за мир. Дроны за всё остальное.",
     "stats": {"strength": 5, "cunning": 8, "charisma": 10, "resources": 8, "luck": 8, "madness": 3},
     "attacks": [
         {"name": "Yes We Can", "type": "media", "power": 90},
         {"name": "Дрон-страйк", "type": "military", "power": 85},
         {"name": "Обамакэр", "type": "diplomatic", "power": 78},
         {"name": "Микрофон-дроп", "type": "provocation", "power": 72},
         {"name": "Нобелевская речь", "type": "diplomatic", "power": 70},
         {"name": "Баскетбольный бросок", "type": "provocation", "power": 65},
     ]},
    {"id": "reagan", "name": "Рональд Рейган", "icon": "🤠", "category": "🇺🇸 США",
     "era": "1981–1989", "desc": "Голливудский ковбой в Белом доме. Развалил СССР одной улыбкой.",
     "stats": {"strength": 6, "cunning": 7, "charisma": 9, "resources": 8, "luck": 7, "madness": 5},
     "attacks": [
         {"name": "Звёздные войны", "type": "military", "power": 90},
         {"name": "Снесите эту стену!", "type": "diplomatic", "power": 85},
         {"name": "Голливудская улыбка", "type": "media", "power": 75},
         {"name": "Рейганомика", "type": "economic", "power": 82},
         {"name": "Ковбойский выстрел", "type": "military", "power": 78},
         {"name": "Шутка про бомбёжку", "type": "provocation", "power": 70},
     ]},
    {"id": "roosevelt", "name": "Франклин Рузвельт", "icon": "🦅", "category": "🇺🇸 США",
     "era": "1933–1945", "desc": "Новый курс, Вторая мировая, 4 срока подряд. С инвалидного кресла.",
     "stats": {"strength": 7, "cunning": 9, "charisma": 9, "resources": 9, "luck": 8, "madness": 5},
     "attacks": [
         {"name": "Новый курс", "type": "economic", "power": 90},
         {"name": "День Д", "type": "military", "power": 95},
         {"name": "Кресло-ракета", "type": "military", "power": 80},
         {"name": "Радиообращение", "type": "media", "power": 85},
         {"name": "Ленд-лиз", "type": "diplomatic", "power": 82},
         {"name": "Четыре свободы", "type": "diplomatic", "power": 78},
     ]},
    {"id": "kennedy", "name": "Джон Кеннеди", "icon": "🎩", "category": "🇺🇸 США",
     "era": "1961–1963", "desc": "Камелот. Красавец, космос, Куба, кабриолет... ой.",
     "stats": {"strength": 6, "cunning": 7, "charisma": 10, "resources": 8, "luck": 2, "madness": 4},
     "attacks": [
         {"name": "Кубинский кризис", "type": "military", "power": 92},
         {"name": "Мы полетим на Луну!", "type": "media", "power": 88},
         {"name": "Берлинская речь", "type": "diplomatic", "power": 85},
         {"name": "Обаяние Камелота", "type": "media", "power": 80},
         {"name": "Мирный корпус", "type": "diplomatic", "power": 70},
         {"name": "Залив Свиней", "type": "military", "power": 55},
     ]},
    {"id": "lincoln", "name": "Авраам Линкольн", "icon": "🎭", "category": "🇺🇸 США",
     "era": "1861–1865", "desc": "Освободитель. Дровосек. Борец. Шляпа 25 см.",
     "stats": {"strength": 8, "cunning": 8, "charisma": 10, "resources": 6, "luck": 3, "madness": 4},
     "attacks": [
         {"name": "Прокламация свободы", "type": "diplomatic", "power": 95},
         {"name": "Геттисбергская речь", "type": "media", "power": 90},
         {"name": "Северная армия", "type": "military", "power": 88},
         {"name": "Борцовский приём", "type": "military", "power": 75},
         {"name": "Топор дровосека", "type": "military", "power": 70},
         {"name": "Шляпный трюк", "type": "provocation", "power": 60},
     ]},

    # ═══════════════ 🇺🇦 УКРАИНА (5) ═══════════════
    {"id": "zelensky", "name": "Владимир Зеленский", "icon": "🎬", "category": "🇺🇦 Украина",
     "era": "2019–н.в.", "desc": "Из КВН в президенты. Слуга народа IRL. Зелёная футболка — броня +100.",
     "stats": {"strength": 6, "cunning": 7, "charisma": 9, "resources": 5, "luck": 8, "madness": 6},
     "attacks": [
         {"name": "Слуга народа", "type": "media", "power": 85},
         {"name": "Мне нужны патроны!", "type": "military", "power": 82},
         {"name": "Зум-дипломатия", "type": "diplomatic", "power": 78},
         {"name": "Селфи на передовой", "type": "media", "power": 80},
         {"name": "Квартал 95", "type": "provocation", "power": 70},
         {"name": "Зелёная футболка", "type": "media", "power": 75},
     ]},
    {"id": "bandera", "name": "Степан Бандера", "icon": "🔱", "category": "🇺🇦 Украина",
     "era": "1909–1959", "desc": "Герой для одних, злодей для других. Партизан-максималист.",
     "stats": {"strength": 8, "cunning": 7, "charisma": 7, "resources": 3, "luck": 4, "madness": 9},
     "attacks": [
         {"name": "Партизанская засада", "type": "military", "power": 85},
         {"name": "Красно-чёрный флаг", "type": "provocation", "power": 78},
         {"name": "Подполье", "type": "intrigue", "power": 82},
         {"name": "Националистический клич", "type": "media", "power": 75},
         {"name": "Лесные братья", "type": "military", "power": 80},
         {"name": "Сопротивление", "type": "military", "power": 72},
     ]},
    {"id": "yushchenko", "name": "Виктор Ющенко", "icon": "🍊", "category": "🇺🇦 Украина",
     "era": "2005–2010", "desc": "Оранжевая революция. Пасечник. Выжил после диоксина.",
     "stats": {"strength": 4, "cunning": 5, "charisma": 6, "resources": 4, "luck": 3, "madness": 3},
     "attacks": [
         {"name": "Оранжевая революция", "type": "media", "power": 80},
         {"name": "Выжил после яда", "type": "provocation", "power": 70},
         {"name": "Пасека", "type": "economic", "power": 45},
         {"name": "Европейский вектор", "type": "diplomatic", "power": 60},
         {"name": "Голодомор-мемориал", "type": "media", "power": 65},
         {"name": "Банковская реформа", "type": "economic", "power": 55},
     ]},
    {"id": "kuchma", "name": "Леонид Кучма", "icon": "📼", "category": "🇺🇦 Украина",
     "era": "1994–2005", "desc": "Кассетный скандал. «Украина — не Россия». Ракеты строил в СССР.",
     "stats": {"strength": 5, "cunning": 7, "charisma": 4, "resources": 6, "luck": 5, "madness": 4},
     "attacks": [
         {"name": "Кассетный скандал", "type": "intrigue", "power": 78},
         {"name": "Кучма ни при чём", "type": "intrigue", "power": 72},
         {"name": "Минские соглашения", "type": "diplomatic", "power": 70},
         {"name": "Днепропетровский клан", "type": "economic", "power": 75},
         {"name": "Украина — не Россия", "type": "media", "power": 65},
         {"name": "Ракетный завод", "type": "military", "power": 68},
     ]},
    {"id": "poroshenko", "name": "Пётр Порошенко", "icon": "🍫", "category": "🇺🇦 Украина",
     "era": "2014–2019", "desc": "Шоколадный король. Армия-мова-віра. Рошен — оружие массового ожирения.",
     "stats": {"strength": 5, "cunning": 6, "charisma": 5, "resources": 8, "luck": 5, "madness": 4},
     "attacks": [
         {"name": "Шоколадная бомба", "type": "economic", "power": 75},
         {"name": "Безвиз", "type": "diplomatic", "power": 80},
         {"name": "Армія-мова-віра", "type": "media", "power": 78},
         {"name": "Томос", "type": "diplomatic", "power": 72},
         {"name": "Рошен-удар", "type": "economic", "power": 70},
         {"name": "Минские переговоры", "type": "diplomatic", "power": 65},
     ]},

    # ═══════════════ :material/public: МИР (4) ═══════════════
    {"id": "merkel", "name": "Ангела Меркель", "icon": "🇩🇪", "category": ":material/public: Мир",
     "era": "2005–2021", "desc": "Мутти. 16 лет тишины и стабильности. Ромбик руками — фирменный знак.",
     "stats": {"strength": 4, "cunning": 9, "charisma": 7, "resources": 9, "luck": 7, "madness": 2},
     "attacks": [
         {"name": "Wir schaffen das", "type": "diplomatic", "power": 82},
         {"name": "Ромбик Меркель", "type": "provocation", "power": 60},
         {"name": "Северный поток", "type": "economic", "power": 85},
         {"name": "Бюджетная дисциплина", "type": "economic", "power": 80},
         {"name": "Терпение", "type": "intrigue", "power": 75},
         {"name": "Тихий шёпот", "type": "intrigue", "power": 70},
     ]},
    {"id": "macron", "name": "Эмманюэль Макрон", "icon": "🥖", "category": ":material/public: Мир",
     "era": "2017–н.в.", "desc": "Юный Наполеон. Жена старше на 25 лет. Жёлтые жилеты — его кошмар.",
     "stats": {"strength": 4, "cunning": 7, "charisma": 8, "resources": 7, "luck": 6, "madness": 5},
     "attacks": [
         {"name": "Jupiter-удар", "type": "provocation", "power": 75},
         {"name": "Реформа по-французски", "type": "economic", "power": 70},
         {"name": "Жёлтые жилеты", "type": "military", "power": 65},
         {"name": "Молодость и дерзость", "type": "media", "power": 72},
         {"name": "Ядерный арсенал", "type": "military", "power": 80},
         {"name": "Европейская армия", "type": "diplomatic", "power": 78},
     ]},
    {"id": "xi", "name": "Си Цзиньпин", "icon": "🐼", "category": ":material/public: Мир",
     "era": "2012–н.в.", "desc": "Винни-Пух, которого нельзя называть Винни-Пухом. Великий файрвол и общее процветание.",
     "stats": {"strength": 6, "cunning": 10, "charisma": 6, "resources": 10, "luck": 7, "madness": 5},
     "attacks": [
         {"name": "Великий файрвол", "type": "intrigue", "power": 90},
         {"name": "Социальный рейтинг", "type": "intrigue", "power": 88},
         {"name": "Пояс и путь", "type": "economic", "power": 92},
         {"name": "Цензура интернета", "type": "media", "power": 85},
         {"name": "Панда-дипломатия", "type": "diplomatic", "power": 70},
         {"name": "Общее процветание", "type": "economic", "power": 82},
     ]},
    {"id": "modi", "name": "Нарендра Моди", "icon": ":material/favorite:", "category": ":material/public: Мир",
     "era": "2014–н.в.", "desc": "Йога на лужайке ООН. 1.4 миллиарда подписчиков.",
     "stats": {"strength": 5, "cunning": 7, "charisma": 8, "resources": 7, "luck": 6, "madness": 4},
     "attacks": [
         {"name": "Йога-приём", "type": "provocation", "power": 65},
         {"name": "Демонетизация", "type": "economic", "power": 80},
         {"name": "Хинду-национализм", "type": "media", "power": 75},
         {"name": "Космическая программа", "type": "military", "power": 78},
         {"name": "Чайная дипломатия", "type": "diplomatic", "power": 70},
         {"name": "Цифровая Индия", "type": "economic", "power": 72},
     ]},

    # ═══════════════ :material/swords: ЛЕГЕНДЫ (6) ═══════════════
    {"id": "churchill", "name": "Уинстон Черчилль", "icon": "🎩", "category": ":material/swords: Легенды",
     "era": "1940–1945, 1951–1955", "desc": "Кровь, пот и слёзы. Сигара, виски и V-знак. Бульдог империи.",
     "stats": {"strength": 7, "cunning": 9, "charisma": 10, "resources": 8, "luck": 8, "madness": 6},
     "attacks": [
         {"name": "Кровь, пот и слёзы", "type": "media", "power": 90},
         {"name": "Дюнкерк", "type": "military", "power": 85},
         {"name": "V-знак Победы", "type": "media", "power": 82},
         {"name": "Сигарный дым", "type": "provocation", "power": 65},
         {"name": "Железный занавес", "type": "diplomatic", "power": 88},
         {"name": "Бомбёжка Дрездена", "type": "military", "power": 90},
     ]},
    {"id": "hitler", "name": "Адольф Гитлер", "icon": "💀", "category": ":material/swords: Легенды",
     "era": "1933–1945", "desc": "Проиграл войну, но сначала начал её. Вегетарианец с усиками.",
     "stats": {"strength": 6, "cunning": 7, "charisma": 9, "resources": 7, "luck": 3, "madness": 10},
     "attacks": [
         {"name": "Блицкриг", "type": "military", "power": 92},
         {"name": "Пропаганда Геббельса", "type": "media", "power": 88},
         {"name": "Крик с трибуны", "type": "provocation", "power": 80},
         {"name": "Автобаны", "type": "economic", "power": 65},
         {"name": "Операция Барбаросса", "type": "military", "power": 90},
         {"name": "Бункер-финал", "type": "provocation", "power": 30},
     ]},
    {"id": "napoleon", "name": "Наполеон Бонапарт", "icon": "👑", "category": ":material/swords: Легенды",
     "era": "1799–1815", "desc": "Маленький капрал с большими амбициями. Завоевал Европу, проиграл зиме.",
     "stats": {"strength": 9, "cunning": 9, "charisma": 9, "resources": 7, "luck": 4, "madness": 7},
     "attacks": [
         {"name": "Аустерлиц", "type": "military", "power": 95},
         {"name": "Кодекс Наполеона", "type": "diplomatic", "power": 85},
         {"name": "Маленький, но грозный", "type": "provocation", "power": 70},
         {"name": "Корсиканская хитрость", "type": "intrigue", "power": 78},
         {"name": "Шляпа императора", "type": "media", "power": 65},
         {"name": "Ватерлоо наоборот", "type": "military", "power": 80},
     ]},
    {"id": "alexander", "name": "Александр Македонский", "icon": ":material/swords:", "category": ":material/swords: Легенды",
     "era": "336–323 до н.э.", "desc": "Завоевал полмира к 30 годам. Умер от вечеринки (или яда).",
     "stats": {"strength": 10, "cunning": 8, "charisma": 10, "resources": 8, "luck": 7, "madness": 7},
     "attacks": [
         {"name": "Фаланга", "type": "military", "power": 95},
         {"name": "Гордиев узел", "type": "intrigue", "power": 90},
         {"name": "Буцефал-страйк", "type": "military", "power": 88},
         {"name": "Завоевание Персии", "type": "military", "power": 92},
         {"name": "Обожествление", "type": "media", "power": 80},
         {"name": "Пир в Вавилоне", "type": "provocation", "power": 60},
     ]},
    {"id": "mao", "name": "Мао Цзэдун", "icon": "📕", "category": ":material/swords: Легенды",
     "era": "1949–1976", "desc": "Красная книжечка. Большой скачок. Культурная революция. Воробьи не одобряют.",
     "stats": {"strength": 7, "cunning": 8, "charisma": 8, "resources": 7, "luck": 6, "madness": 9},
     "attacks": [
         {"name": "Культурная революция", "type": "provocation", "power": 90},
         {"name": "Большой скачок", "type": "economic", "power": 85},
         {"name": "Красная книжечка", "type": "media", "power": 88},
         {"name": "Народная армия", "type": "military", "power": 92},
         {"name": "Длинный марш", "type": "military", "power": 80},
         {"name": "Сто цветов", "type": "intrigue", "power": 75},
     ]},
    {"id": "mandela", "name": "Нельсон Мандела", "icon": "✊", "category": ":material/swords: Легенды",
     "era": "1994–1999", "desc": "27 лет в тюрьме → президент. Терпение — суперсила.",
     "stats": {"strength": 6, "cunning": 7, "charisma": 10, "resources": 3, "luck": 8, "madness": 3},
     "attacks": [
         {"name": "27 лет терпения", "type": "intrigue", "power": 85},
         {"name": "Радужная нация", "type": "diplomatic", "power": 90},
         {"name": "Кулак свободы", "type": "media", "power": 88},
         {"name": "Примирение", "type": "diplomatic", "power": 82},
         {"name": "Робин-Айленд", "type": "provocation", "power": 70},
         {"name": "Регби-дипломатия", "type": "media", "power": 75},
     ]},
]

# ──────────────────────────────────────────────────────────────
#  СМЕШНЫЕ ПРИЧИНЫ ПОБЕДЫ (маркетолог одобряет)
# ──────────────────────────────────────────────────────────────
FUNNY_REASONS = [
    "{winner} победил, потому что {loser} отвлёкся на уведомление в Telegram",
    "{winner} загуглил «как победить {loser}» — и сработало",
    "Шёл {year} год. У {winner} был VPN, а у {loser} — нет",
    "{loser} был сильнее, но {winner} знал пароль от его Wi-Fi",
    "{winner} победил силой мысли. {loser} не думал вообще",
    "По данным британских учёных, {winner} на 73% эффективнее {loser}",
    "{winner} подписан на {loser} в TikTok и знал все его приёмы",
    "{loser} хотел договориться, но {winner} уже нажал красную кнопку",
    "{winner} использовал запрещённый приём — показал {loser} его рейтинг",
    "У {loser} разрядился телефон в решающий момент — GG",
    "{winner} выиграл на чистом безумии. Нейросеть подтверждает.",
    "{loser} поскользнулся на банановой кожуре. {winner} подложил.",
    "{winner} прочитал книгу «Искусство войны». {loser} смотрел TikTok.",
    "Астрологи объявили: Меркурий ретроградный. {loser} пострадал вдвойне.",
    "Алгоритм решил, что {winner} больше заслуживает победу. Мы не спорим.",
    "{winner} активировал режим берсерка. {loser} активировал режим паники.",
    "По секрету: {loser} забыл надеть носки. На войне это критично.",
    "{winner} применил тактику «непредсказуемый идиот». Это сработало.",
    "ChatGPT предсказал победу {loser}. Как обычно, ошибся.",
    "{loser} понадеялся на дипломатию. {winner} понадеялся на кулак.",
    "Источник в Кремле сообщил: {winner} тренировался по ночам.",
    "{winner} был сильнее, потому что позавтракал. {loser} пропустил завтрак.",
    "Секретные документы WikiLeaks подтверждают: {winner} > {loser}.",
    "{loser} пытался позвонить другу, но друг болел за {winner}.",
    "{winner} нашёл чит-код. {loser} играл честно. Мораль: не играй честно.",
    "Генштаб {loser} заседал 3 часа. Генштаб {winner} просто атаковал.",
    "По итогам голосования 146% аудитории, {winner} — абсолютный чемпион.",
    "{loser} отвлёкся на мем про себя. {winner} воспользовался моментом.",
    "ИИ-аналитик присвоил {winner} рейтинг «SIGMA». {loser} получил «бета».",
    "Разведка {winner} перехватила план {loser}. План был написан на салфетке.",
]

# ──────────────────────────────────────────────────────────────
#  БОЕВАЯ МОДЕЛЬ (30/70)
# ──────────────────────────────────────────────────────────────
def _calc_power(fighter: dict, chosen_attacks: list) -> float:
    """Рассчитать силу бойца: сумма статов + средняя мощь выбранных атак."""
    stat_sum = sum(fighter["stats"].values())
    if chosen_attacks:
        atk_avg = sum(a["power"] for a in chosen_attacks) / len(chosen_attacks)
    else:
        atk_avg = 50
    return stat_sum * 1.5 + atk_avg


def evaluate_battle(
    fighter_a: dict, attacks_a: list,
    fighter_b: dict, attacks_b: list,
    user_bet: str,
) -> dict:
    """
    Бой двух политиков.
    user_bet = id бойца, на которого ставит пользователь.
    70% — пользователь проигрывает, 30% — выигрывает.
    """
    power_a = _calc_power(fighter_a, attacks_a)
    power_b = _calc_power(fighter_b, attacks_b)
    total = power_a + power_b or 1
    pct_a = round(power_a / total * 100, 1)
    pct_b = round(power_b / total * 100, 1)

    # 30/70 рулетка
    roll = random.random()
    if roll < 0.30:
        # Пользователь выигрывает ставку
        winner_id = user_bet
    else:
        # Сервис выигрывает — противоположный боец
        winner_id = fighter_b["id"] if user_bet == fighter_a["id"] else fighter_a["id"]

    winner = fighter_a if winner_id == fighter_a["id"] else fighter_b
    loser = fighter_b if winner_id == fighter_a["id"] else fighter_a
    user_won = (winner_id == user_bet)

    # Генерация боевого лога — 3 раунда (по 1 атаке каждого)
    rounds = []
    for i in range(3):
        atk_a = attacks_a[i] if i < len(attacks_a) else attacks_a[0]
        atk_b = attacks_b[i] if i < len(attacks_b) else attacks_b[0]
        # Чуть рандома для красоты
        dmg_a = atk_a["power"] + random.randint(-15, 15)
        dmg_b = atk_b["power"] + random.randint(-15, 15)
        rounds.append({
            "a_attack": atk_a["name"], "a_dmg": max(0, dmg_a),
            "b_attack": atk_b["name"], "b_dmg": max(0, dmg_b),
            "round_winner": "a" if dmg_a > dmg_b else ("b" if dmg_b > dmg_a else "draw"),
        })

    # Смешная причина
    reason = random.choice(FUNNY_REASONS).format(
        winner=winner["name"], loser=loser["name"], year=2025,
    )

    return {
        "winner": winner,
        "loser": loser,
        "user_won": user_won,
        "pct_a": pct_a,
        "pct_b": pct_b,
        "rounds": rounds,
        "reason": reason,
    }


# ──────────────────────────────────────────────────────────────
#  CSS — CYBERPUNK × KAWAII
# ──────────────────────────────────────────────────────────────
_PAGE_CSS = '''<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

[data-testid="stSidebar"],[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],footer,#MainMenu{display:none!important;}
.main .block-container{padding-top:0!important;max-width:1200px!important;}

/* ═══ ГЛОБАЛЬНЫЙ ФОН — кибер-сетка ═══ */
.stApp,.main,[data-testid="stAppViewContainer"]{
  background-color:#08080f!important;
  background-image:
    linear-gradient(rgba(255,107,157,.03) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,240,255,.03) 1px,transparent 1px),
    radial-gradient(ellipse 80% 60% at 50% 0%,rgba(180,110,255,.12) 0%,transparent 60%),
    radial-gradient(ellipse 60% 40% at 0% 100%,rgba(255,107,157,.08) 0%,transparent 50%),
    radial-gradient(ellipse 60% 40% at 100% 100%,rgba(0,240,255,.08) 0%,transparent 50%)
    !important;
  background-size:60px 60px,60px 60px,100% 100%,100% 100%,100% 100%!important;
}
.stApp *{font-family:'Rajdhani','Segoe UI',sans-serif!important;}

/* ═══ ЗАГОЛОВОК ═══ */
.pk-hero{
  text-align:center;padding:28px 20px 22px;margin-bottom:20px;
  background:linear-gradient(180deg,rgba(180,110,255,.1) 0%,rgba(8,8,15,.95) 100%);
  border-bottom:2px solid rgba(255,107,157,.3);
  position:relative;overflow:hidden;
}
.pk-hero::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,#ff6b9d,#00f0ff,#b46eff,transparent);
}
.pk-title{
  font-family:'Orbitron',monospace!important;
  font-size:32px;font-weight:900;
  background:linear-gradient(135deg,#ff6b9d,#b46eff,#00f0ff);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  text-shadow:none;margin:0 0 6px;letter-spacing:.05em;
  animation:titleGlow 3s ease-in-out infinite;
}
@keyframes titleGlow{
  0%,100%{filter:drop-shadow(0 0 8px rgba(255,107,157,.5));}
  50%{filter:drop-shadow(0 0 20px rgba(180,110,255,.8));}
}
.pk-subtitle{
  font-size:14px;color:rgba(255,107,157,.6);letter-spacing:.08em;margin:0;
}

/* ═══ КАРТОЧКА ПОЛИТИКА ═══ */
.pk-card{
  position:relative;margin-bottom:14px;
  background:rgba(16,14,28,.92);
  border:1.5px solid rgba(180,110,255,.25);
  border-radius:16px;
  box-shadow:0 0 20px rgba(180,110,255,.1),inset 0 0 30px rgba(0,0,0,.5);
  padding:14px 16px;overflow:hidden;
  transition:border-color .3s,box-shadow .3s;
}
.pk-card:hover{
  border-color:rgba(255,107,157,.5);
  box-shadow:0 0 30px rgba(255,107,157,.2),inset 0 0 30px rgba(0,0,0,.5);
}
.pk-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,rgba(0,240,255,.4),transparent);
}

/* ── Шапка карточки ── */
.pk-header{display:flex;gap:14px;align-items:flex-start;margin-bottom:10px;}
.pk-portrait{
  flex-shrink:0;width:80px;height:80px;
  border:2px solid rgba(255,107,157,.4);border-radius:12px;
  background:radial-gradient(ellipse at 50% 30%,rgba(180,110,255,.15),rgba(8,8,15,.9));
  display:flex;align-items:center;justify-content:center;
  font-size:48px;line-height:1;
  box-shadow:0 0 15px rgba(255,107,157,.2);
}
.pk-name{
  font-family:'Orbitron',monospace!important;
  font-size:16px;font-weight:700;
  color:#ff6b9d;margin:0 0 2px;
}
.pk-era{font-size:11px;color:rgba(0,240,255,.6);letter-spacing:.06em;}
.pk-desc{font-size:12px;color:rgba(255,255,255,.5);margin:4px 0 0;line-height:1.4;}
.pk-category{
  font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:rgba(180,110,255,.7);margin-top:2px;
}

/* ── Стат-бары ── */
.pk-stats{margin:8px 0;}
.pk-stat-row{display:flex;align-items:center;gap:8px;margin-bottom:4px;}
.pk-stat-label{
  min-width:100px;font-size:11px;font-weight:600;color:rgba(255,255,255,.6);
}
.pk-stat-track{
  flex:1;height:14px;background:rgba(255,255,255,.05);border-radius:7px;
  overflow:hidden;position:relative;
}
.pk-stat-fill{
  height:100%;border-radius:7px;
  transition:width .5s ease;position:relative;
}
.pk-stat-val{
  position:absolute;right:6px;top:50%;transform:translateY(-50%);
  font-size:10px;font-weight:700;color:#fff;text-shadow:0 0 4px rgba(0,0,0,.8);
}

/* ── Атаки ── */
.pk-attacks{margin:8px 0 4px;}
.pk-atk-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;}
.pk-atk-btn{
  padding:8px 10px;border-radius:10px;cursor:pointer;
  border:1.5px solid rgba(0,240,255,.2);
  background:rgba(0,240,255,.05);
  transition:all .2s;font-size:11px;color:rgba(255,255,255,.7);
}
.pk-atk-btn:hover{
  border-color:rgba(0,240,255,.5);background:rgba(0,240,255,.12);
  box-shadow:0 0 12px rgba(0,240,255,.2);
}
.pk-atk-btn.selected{
  border-color:#ff6b9d;background:rgba(255,107,157,.15);
  box-shadow:0 0 12px rgba(255,107,157,.3);color:#ff6b9d;
}
.pk-atk-power{font-weight:700;color:#00f0ff;}
.pk-atk-type{font-size:9px;color:rgba(180,110,255,.6);}

/* ═══ СЕКЦИИ ═══ */
.pk-section{
  font-family:'Orbitron',monospace!important;
  font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  color:rgba(0,240,255,.5);margin:10px 0 6px;
  border-bottom:1px solid rgba(0,240,255,.1);padding-bottom:4px;
}

/* ═══ VS ═══ */
.pk-vs{
  font-family:'Orbitron',monospace!important;
  font-size:36px;font-weight:900;text-align:center;
  background:linear-gradient(180deg,#ff6b9d,#b46eff);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  padding:40px 0;
  animation:vsPulse 2s ease-in-out infinite;
}
@keyframes vsPulse{
  0%,100%{transform:scale(1);filter:drop-shadow(0 0 4px rgba(255,107,157,.3));}
  50%{transform:scale(1.1);filter:drop-shadow(0 0 16px rgba(180,110,255,.6));}
}

/* ═══ СТАВКИ ═══ */
.pk-bet-panel{
  background:rgba(16,14,28,.95);border:1.5px solid rgba(255,215,0,.3);
  border-radius:14px;padding:16px;margin:16px 0;text-align:center;
  box-shadow:0 0 20px rgba(255,215,0,.08);
}
.pk-coins{
  font-family:'Orbitron',monospace!important;
  font-size:22px;font-weight:700;color:#ffd700;
  text-shadow:0 0 10px rgba(255,215,0,.5);
}

/* ═══ РЕЗУЛЬТАТ ═══ */
.pk-result{
  background:rgba(16,14,28,.95);border-radius:16px;
  border:1.5px solid rgba(180,110,255,.3);
  padding:20px;margin:20px 0;overflow:hidden;position:relative;
}
.pk-result::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,#ff6b9d,#b46eff,#00f0ff);
}
.pk-result-title{
  font-family:'Orbitron',monospace!important;
  font-size:14px;font-weight:700;color:#00f0ff;text-align:center;
  letter-spacing:.1em;margin-bottom:12px;
}
.pk-winner-banner{
  font-family:'Orbitron',monospace!important;
  font-size:18px;font-weight:700;text-align:center;
  padding:12px;border-radius:10px;margin:10px 0;
  letter-spacing:.08em;
}
.pk-winner-banner.win{
  color:#00ff88;border:1.5px solid rgba(0,255,136,.3);
  background:rgba(0,255,136,.08);
  text-shadow:0 0 12px rgba(0,255,136,.5);
}
.pk-winner-banner.lose{
  color:#ff4466;border:1.5px solid rgba(255,68,102,.3);
  background:rgba(255,68,102,.08);
  text-shadow:0 0 12px rgba(255,68,102,.5);
}

/* ── Полоска сравнения ── */
.pk-bar-track{
  display:flex;height:24px;border-radius:12px;overflow:hidden;
  background:rgba(255,255,255,.05);margin:10px 0;
}
.pk-bar-a{
  background:linear-gradient(90deg,#ff6b9d,#b46eff);
  display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;color:#fff;
}
.pk-bar-b{
  background:linear-gradient(90deg,#00f0ff,#00cc88);
  display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;color:#fff;
}

/* ── Раунды ── */
.pk-round{
  display:flex;align-items:center;gap:8px;margin:6px 0;
  font-size:12px;color:rgba(255,255,255,.6);
}
.pk-round-badge{
  width:24px;height:24px;border-radius:6px;display:flex;
  align-items:center;justify-content:center;font-size:10px;font-weight:700;
  border:1px solid rgba(180,110,255,.3);color:#b46eff;flex-shrink:0;
}

/* ── Причина ── */
.pk-reason{
  font-size:14px;color:rgba(255,107,157,.8);
  text-align:center;margin:14px 0;padding:12px;
  background:rgba(255,107,157,.05);border-radius:10px;
  border:1px solid rgba(255,107,157,.15);
  font-style:italic;
}

/* ═══ АНИМАЦИИ БОЯ ═══ */
@keyframes winnerSmash{
  0%{transform:scale(1) translateX(0);}
  20%{transform:scale(1.2) translateX(30px);}
  40%{transform:scale(1.15) translateX(-10px);}
  60%{transform:scale(1.25) translateX(15px);}
  80%{transform:scale(1.1) translateX(0);}
  100%{transform:scale(1.05) translateX(0);}
}
@keyframes loserCrush{
  0%{transform:scale(1);filter:brightness(1);}
  20%{transform:scale(1.1) rotate(5deg);filter:brightness(2) hue-rotate(30deg);}
  40%{transform:scale(0.8) rotate(-8deg);filter:brightness(0.5);}
  60%{transform:scale(0.6) rotate(10deg);filter:blur(2px) brightness(0.3);}
  80%{transform:scale(0.5) rotate(-5deg);filter:blur(4px) brightness(0.2) grayscale(1);}
  100%{transform:scale(0.4);filter:blur(6px) brightness(0.2) grayscale(1);}
}
@keyframes laurelAppear{
  0%{opacity:0;transform:scale(0) rotate(-30deg);}
  60%{opacity:1;transform:scale(1.2) rotate(5deg);}
  100%{opacity:1;transform:scale(1) rotate(0);}
}
@keyframes drawPulse{
  0%,100%{transform:scale(1);filter:brightness(1);}
  50%{transform:scale(1.05);filter:brightness(1.3);}
}
.pk-winner-anim{
  animation:winnerSmash 1.2s cubic-bezier(.36,.07,.19,.97) both;
  position:relative;z-index:2;
}
.pk-loser-anim{
  animation:loserCrush 1.4s cubic-bezier(.36,.07,.19,.97) forwards;
  position:relative;
}
.pk-draw-anim{animation:drawPulse 1s ease-in-out 2;}
.pk-laurel{
  font-size:32px;text-align:center;
  animation:laurelAppear .8s ease-out .5s both;
}

/* ── Portait Stage ── */
.pk-stage{
  display:flex;align-items:flex-start;justify-content:center;
  gap:30px;margin:16px 0;padding:16px 0;
}
.pk-stage-box{
  display:flex;flex-direction:column;align-items:center;gap:6px;
  min-width:160px;
}
.pk-stage-emoji{font-size:80px;line-height:1;text-align:center;}
.pk-stage-name{
  font-family:'Orbitron',monospace!important;
  font-size:14px;font-weight:700;text-align:center;
}
.pk-stage-score{
  font-family:'Orbitron',monospace!important;
  font-size:22px;font-weight:900;text-align:center;
  color:#ffd700;text-shadow:0 0 8px rgba(255,215,0,.4);
}
.winner-stage .pk-stage-emoji{
  filter:drop-shadow(0 0 20px rgba(255,107,157,.6));
  animation:titleGlow 2s ease-in-out infinite;
}
.winner-stage .pk-stage-name{color:#00ff88;}
.loser-stage .pk-stage-emoji{filter:grayscale(.8) brightness(.4);}
.loser-stage .pk-stage-name{color:#444;}

/* ═══ КНОПКИ ═══ */
[data-testid="stButton"] button{
  font-family:'Orbitron',monospace!important;font-weight:700!important;
  letter-spacing:.1em!important;text-transform:uppercase!important;
  background:linear-gradient(135deg,rgba(255,107,157,.15),rgba(180,110,255,.15))!important;
  border:1.5px solid rgba(255,107,157,.4)!important;color:#ff6b9d!important;
  border-radius:10px!important;
  box-shadow:0 0 12px rgba(255,107,157,.15)!important;
  transition:all .3s!important;
}
[data-testid="stButton"] button:hover{
  background:linear-gradient(135deg,rgba(255,107,157,.25),rgba(180,110,255,.25))!important;
  box-shadow:0 0 24px rgba(255,107,157,.3)!important;
  color:#fff!important;border-color:#ff6b9d!important;
}

/* ═══ ВИДЖЕТЫ ═══ */
[data-testid="stRadio"] label,[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
.stMarkdown p,.stMarkdown h3{
  font-family:'Rajdhani',sans-serif!important;color:rgba(255,255,255,.7)!important;
}
[data-baseweb="select"] *,[data-baseweb="select"] input{
  font-family:'Rajdhani',sans-serif!important;
  background:rgba(16,14,28,.9)!important;color:#00f0ff!important;
  border-color:rgba(180,110,255,.3)!important;
}
hr{border:none;border-top:1px solid rgba(180,110,255,.15);margin:14px 0;}

/* ═══ АДАПТИВ ═══ */
@media(max-width:900px){
  .pk-title{font-size:20px;}
  .pk-stage{gap:10px;}
  .pk-stage-emoji{font-size:50px;}
  .pk-atk-grid{grid-template-columns:1fr;}
}
</style>'''

# ── Цвета статов ──
STAT_COLORS = {
    "strength":  "#ff4466",
    "cunning":   "#b46eff",
    "charisma":  "#ff6b9d",
    "resources": "#ffd700",
    "luck":      "#00ff88",
    "madness":   "#00f0ff",
}


# ──────────────────────────────────────────────────────────────
#  РЕНДЕР КАРТОЧКИ
# ──────────────────────────────────────────────────────────────
def _render_char_card(p: dict) -> str:
    """HTML-карточка политика."""
    # Статы
    stats_html = ""
    for key, label in STAT_LABELS.items():
        val = p["stats"].get(key, 0)
        color = STAT_COLORS.get(key, "#888")
        pct = val * 10
        stats_html += (
            f'<div class="pk-stat-row">'
            f'<div class="pk-stat-label">{label}</div>'
            f'<div class="pk-stat-track">'
            f'<div class="pk-stat-fill" style="width:{pct}%;background:{color};">'
            f'<span class="pk-stat-val">{val}</span>'
            f'</div></div></div>'
        )

    # Атаки
    attacks_html = ""
    for i, atk in enumerate(p["attacks"]):
        type_label = ATTACK_TYPE_LABELS.get(atk["type"], atk["type"])
        attacks_html += (
            f'<div class="pk-atk-btn" data-idx="{i}">'
            f'{atk["name"]} '
            f'<span class="pk-atk-power">💥{atk["power"]}</span><br>'
            f'<span class="pk-atk-type">{type_label}</span>'
            f'</div>'
        )

    return (
        f'<div class="pk-card">'
        f'<div class="pk-header">'
        f'<div class="pk-portrait">{p["icon"]}</div>'
        f'<div>'
        f'<div class="pk-name">{p["name"]}</div>'
        f'<div class="pk-category">{p["category"]}</div>'
        f'<div class="pk-era">{p["era"]}</div>'
        f'<div class="pk-desc">{p["desc"]}</div>'
        f'</div></div>'
        f'<div class="pk-section">:material/dashboard: Характеристики</div>'
        f'<div class="pk-stats">{stats_html}</div>'
        f'<div class="pk-section">⚡ Атаки (выбери 3)</div>'
        f'<div class="pk-atk-grid">{attacks_html}</div>'
        f'</div>'
    )


# ──────────────────────────────────────────────────────────────
#  ГЛАВНАЯ СТРАНИЦА
# ──────────────────────────────────────────────────────────────
def render_politicians_page() -> None:
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)

    # ── Заголовок ──
    st.markdown(
        '<div class="pk-hero">'
        '<div class="pk-title">⚡ ПОЛИТИКИ: БИТВА ⚡</div>'
        '<p class="pk-subtitle">✦ Выбери бойцов · Назначь атаки · Поставь монеты · Сразись! ✦</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Инициализация монет ──
    if "coins" not in st.session_state:
        st.session_state.coins = 1000

    # ── Фильтр по категории ──
    cat_filter = st.radio(
        "Фракция",
        ["Все"] + CATEGORIES,
        horizontal=True,
        key="cat_filter",
    )
    if cat_filter == "Все":
        pool = POLITICIANS
    else:
        pool = [p for p in POLITICIANS if p["category"] == cat_filter]

    # ── Выбор бойцов ──
    col_a, col_vs, col_b = st.columns([5, 1, 5])

    with col_a:
        st.markdown("### :red[:material/circle:] Боец A")
        a_idx = st.selectbox(
            "Выбери бойца",
            range(len(pool)),
            format_func=lambda i: f"{pool[i]['icon']} {pool[i]['name']}",
            key="sel_a",
        )
        fighter_a = pool[a_idx]
        st.markdown(_render_char_card(fighter_a), unsafe_allow_html=True)

        # Выбор 3 атак
        atk_a_options = [
            f"{a['name']} (💥{a['power']})" for a in fighter_a["attacks"]
        ]
        sel_atk_a = st.multiselect(
            "Выбери 3 атаки",
            atk_a_options,
            default=atk_a_options[:3],
            max_selections=3,
            key="atk_a",
        )
        attacks_a = [
            fighter_a["attacks"][atk_a_options.index(s)]
            for s in sel_atk_a if s in atk_a_options
        ]

    with col_vs:
        st.markdown('<div class="pk-vs">VS</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown("### :blue[:material/circle:] Боец B")
        b_idx = st.selectbox(
            "Выбери бойца",
            range(len(pool)),
            format_func=lambda i: f"{pool[i]['icon']} {pool[i]['name']}",
            key="sel_b",
            index=min(1, len(pool) - 1),
        )
        fighter_b = pool[b_idx]
        st.markdown(_render_char_card(fighter_b), unsafe_allow_html=True)

        atk_b_options = [
            f"{a['name']} (💥{a['power']})" for a in fighter_b["attacks"]
        ]
        sel_atk_b = st.multiselect(
            "Выбери 3 атаки",
            atk_b_options,
            default=atk_b_options[:3],
            max_selections=3,
            key="atk_b",
        )
        attacks_b = [
            fighter_b["attacks"][atk_b_options.index(s)]
            for s in sel_atk_b if s in atk_b_options
        ]

    # ── Панель ставок ──
    st.markdown("---")
    st.markdown(
        f'<div class="pk-bet-panel">'
        f'<div class="pk-coins">:material/toll: {st.session_state.coins} монет</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    bet_col1, bet_col2 = st.columns(2)
    with bet_col1:
        user_bet = st.radio(
            "На кого ставишь?",
            [fighter_a["name"], fighter_b["name"]],
            horizontal=True,
            key="user_bet",
        )
    with bet_col2:
        max_bet = max(50, st.session_state.coins)
        bet_amount = st.select_slider(
            "Сумма ставки",
            options=[50, 100, 200, 500, 1000],
            value=min(100, st.session_state.coins),
            key="bet_amount",
        )
        if bet_amount > st.session_state.coins:
            bet_amount = st.session_state.coins

    # ── Кнопка БОЙ ──
    st.markdown("---")
    fc1, fc2, fc3 = st.columns([2, 3, 2])
    with fc2:
        fight = st.button(
            "⚡ НАЧАТЬ БОЙ! ⚡",
            use_container_width=True,
            type="primary",
            disabled=len(attacks_a) == 0 or len(attacks_b) == 0,
        )

    # ── Результат ──
    if fight and attacks_a and attacks_b:
        bet_id = fighter_a["id"] if user_bet == fighter_a["name"] else fighter_b["id"]
        result = evaluate_battle(fighter_a, attacks_a, fighter_b, attacks_b, bet_id)

        # Обновить монеты
        if result["user_won"]:
            st.session_state.coins += bet_amount
            coins_delta = f"+{bet_amount}"
        else:
            st.session_state.coins = max(0, st.session_state.coins - bet_amount)
            coins_delta = f"-{bet_amount}"

        if st.session_state.coins <= 0:
            st.session_state.coins = 100  # страховка от нуля

        winner = result["winner"]
        loser = result["loser"]
        is_a_winner = winner["id"] == fighter_a["id"]

        # Классы анимации
        anim_a = "pk-winner-anim" if is_a_winner else "pk-loser-anim"
        anim_b = "pk-loser-anim" if is_a_winner else "pk-winner-anim"
        box_cls_a = "winner-stage" if is_a_winner else "loser-stage"
        box_cls_b = "winner-stage" if not is_a_winner else "loser-stage"
        laurel_a = '<div class="pk-laurel">👑</div>' if is_a_winner else ""
        laurel_b = '<div class="pk-laurel">👑</div>' if not is_a_winner else ""

        # Портреты с анимацией
        st.markdown(
            f'<div class="pk-stage">'
            f'<div class="pk-stage-box {box_cls_a}">'
            f'{laurel_a}'
            f'<div class="{anim_a}"><div class="pk-stage-emoji">{fighter_a["icon"]}</div></div>'
            f'<div class="pk-stage-name">{fighter_a["name"]}</div>'
            f'<div class="pk-stage-score">{result["pct_a"]}%</div>'
            f'</div>'
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'justify-content:center;padding-top:40px;">'
            f'<div style="font-size:28px;">⚡</div>'
            f'<div style="font-family:Orbitron;font-size:11px;color:rgba(255,107,157,.5);">VS</div>'
            f'</div>'
            f'<div class="pk-stage-box {box_cls_b}">'
            f'{laurel_b}'
            f'<div class="{anim_b}"><div class="pk-stage-emoji">{fighter_b["icon"]}</div></div>'
            f'<div class="pk-stage-name">{fighter_b["name"]}</div>'
            f'<div class="pk-stage-score">{result["pct_b"]}%</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Баннер победы/поражения
        if result["user_won"]:
            banner_cls = "win"
            banner_text = f"🎉 ПОБЕДА! {winner['icon']} {winner['name']} побеждает! {coins_delta} :material/toll:"
        else:
            banner_cls = "lose"
            banner_text = f"💀 ПРОИГРЫШ! {winner['icon']} {winner['name']} побеждает! {coins_delta} :material/toll:"

        st.markdown(
            f'<div class="pk-result">'
            f'<div class="pk-result-title">:material/dashboard: РЕЗУЛЬТАТ БОЯ</div>'
            f'<div class="pk-winner-banner {banner_cls}">{banner_text}</div>',
            unsafe_allow_html=True,
        )

        # Полоска сравнения
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;font-size:12px;'
            f'color:rgba(255,255,255,.5);margin-top:12px;">'
            f'<span>{fighter_a["icon"]} {fighter_a["name"]}</span>'
            f'<span>{fighter_b["icon"]} {fighter_b["name"]}</span></div>'
            f'<div class="pk-bar-track">'
            f'<div class="pk-bar-a" style="width:{result["pct_a"]}%;">{result["pct_a"]}%</div>'
            f'<div class="pk-bar-b" style="width:{result["pct_b"]}%;">{result["pct_b"]}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Раунды
        st.markdown('<div class="pk-section">:material/swords: Ход боя</div>', unsafe_allow_html=True)
        for i, r in enumerate(result["rounds"]):
            r_icon = ":red[:material/circle:]" if r["round_winner"] == "a" else (":blue[:material/circle:]" if r["round_winner"] == "b" else "🤝")
            st.markdown(
                f'<div class="pk-round">'
                f'<div class="pk-round-badge">{i+1}</div>'
                f'{r_icon} '
                f'<span style="color:#ff6b9d;">{r["a_attack"]} ({r["a_dmg"]})</span>'
                f' vs '
                f'<span style="color:#00f0ff;">{r["b_attack"]} ({r["b_dmg"]})</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Смешная причина
        st.markdown(
            f'<div class="pk-reason">💬 {result["reason"]}</div>',
            unsafe_allow_html=True,
        )

        # Баланс
        st.markdown(
            f'<div style="text-align:center;margin-top:10px;">'
            f'<span class="pk-coins">:material/toll: Баланс: {st.session_state.coins} монет</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

render_politicians_page()

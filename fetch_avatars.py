import urllib.request, json, time, re

WIKI_MAP = {
    'trump': 'Donald_Trump',
    'putin': 'Vladimir_Putin',
    'biden': 'Joe_Biden',
    'xi': 'Xi_Jinping',
    'kim': 'Kim_Jong-un',
    'zelensky': 'Volodymyr_Zelensky',
    'macron': 'Emmanuel_Macron',
    'boris': 'Boris_Johnson',
    'merkel': 'Angela_Merkel',
    'modi': 'Narendra_Modi',
    'erdogan': 'Recep_Tayyip_Erdo%C4%9Fan',
    'netanyahu': 'Benjamin_Netanyahu',
    'milei': 'Javier_Milei',
    'lukashenko': 'Alexander_Lukashenko',
    'trudeau': 'Justin_Trudeau',
    'churchill': 'Winston_Churchill',
    'stalin': 'Joseph_Stalin',
    'napoleon': 'Napoleon',
    'lincoln': 'Abraham_Lincoln',
    'jfk': 'John_F._Kennedy',
    'castro': 'Fidel_Castro',
    'thatcher': 'Margaret_Thatcher',
    'mao': 'Mao_Zedong',
    'caesar': 'Julius_Caesar',
    'cleopatra': 'Cleopatra',
    'genghis': 'Genghis_Khan',
    'che': 'Che_Guevara',
    'obama': 'Barack_Obama',
    'lenin': 'Vladimir_Lenin',
    'peter_i': 'Peter_the_Great',
    'gorbachev': 'Mikhail_Gorbachev',
    'yeltsin': 'Boris_Yeltsin',
    'catherine_ii': 'Catherine_the_Great',
    'ivan_terrible': 'Ivan_the_Terrible',
    'yushchenko': 'Viktor_Yushchenko',
    'kuchma': 'Leonid_Kuchma',
    'zhirinovsky': 'Vladimir_Zhirinovsky',
    'reagan': 'Ronald_Reagan',
    'alexander_great': 'Alexander_the_Great',
    'mandela': 'Nelson_Mandela',
    'roosevelt': 'Franklin_D._Roosevelt',
    'tymoshenko': 'Yulia_Tymoshenko',
}

headers = {'User-Agent': 'PoliticalArenaGame/1.0 (educational parody game)'}
results = {}

for fid, wiki in WIKI_MAP.items():
    url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{wiki}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        thumb = data.get('thumbnail', {}).get('source', '')
        if not thumb:
            thumb = data.get('originalimage', {}).get('source', '')
        if thumb:
            thumb = re.sub(r'/\d+px-', '/300px-', thumb)
            results[fid] = thumb
            print(f"OK {fid}: {thumb[:60]}...")
        else:
            results[fid] = ''
            print(f"NO_IMG {fid}")
    except Exception as e:
        results[fid] = ''
        print(f"FAIL {fid}: {e}")
    time.sleep(0.12)

with open('/tmp/wiki_avatars.json', 'w') as f:
    json.dump(results, f, indent=2)

ok = sum(1 for v in results.values() if v)
print(f"\nDone: {ok}/{len(results)} URLs")

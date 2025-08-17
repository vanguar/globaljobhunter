// GlobalJobHunter - Современный JS с анимациями
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupAnimations();
    setupProgressBar();
});

let progressInterval;
let currentProgress = 0;

// Максимально расширенная база данных городов с поддержкой альтернативных названий
const CITIES_DATABASE = {
    'de': {
        'Berlin': ['berlin', 'берлин', 'berlín'],
        'Munich': ['munich', 'munchen', 'münchen', 'мюнхен'],
        'Hamburg': ['hamburg', 'гамбург', 'hambourg'],
        'Cologne': ['cologne', 'koln', 'köln', 'кёльн', 'colonia'],
        'Frankfurt': ['frankfurt', 'франкфурт', 'frankfurta'],
        'Stuttgart': ['stuttgart', 'штутгарт'],
        'Düsseldorf': ['dusseldorf', 'düsseldorf', 'дюссельдорф'],
        'Dortmund': ['dortmund', 'дортмунд'],
        'Essen': ['essen', 'эссен'],
        'Leipzig': ['leipzig', 'лейпциг'],
        'Bremen': ['bremen', 'бремен'],
        'Dresden': ['dresden', 'дрезден'],
        'Hanover': ['hanover', 'hannover', 'ганновер'],
        'Nuremberg': ['nuremberg', 'nurnberg', 'нюрнберг'],
        'Duisburg': ['duisburg', 'дуйсбург'],
        'Bochum': ['bochum', 'бохум'],
        'Wuppertal': ['wuppertal', 'вупперталь'],
        'Bielefeld': ['bielefeld', 'билефельд'],
        'Bonn': ['bonn', 'бонн'],
        'Münster': ['munster', 'münster', 'мюнстер'],
        'Karlsruhe': ['karlsruhe', 'карлсруэ'],
        'Mannheim': ['mannheim', 'мангейм'],
        'Augsburg': ['augsburg', 'аугсбург'],
        'Wiesbaden': ['wiesbaden', 'висбаден'],
        'Gelsenkirchen': ['gelsenkirchen', 'гельзенкирхен'],
        'Mönchengladbach': ['monchengladbach', 'мёнхенгладбах'],
        'Braunschweig': ['braunschweig', 'брауншвейг'],
        'Chemnitz': ['chemnitz', 'хемниц'],
        'Kiel': ['kiel', 'киль'],
        'Aachen': ['aachen', 'ахен'],
        'Halle': ['halle', 'галле'],
        'Magdeburg': ['magdeburg', 'магдебург'],
        'Freiburg': ['freiburg', 'фрайбург'],
        'Krefeld': ['krefeld', 'крефельд'],
        'Lübeck': ['lubeck', 'lübeck', 'любек'],
        'Oberhausen': ['oberhausen', 'оберхаузен'],
        'Erfurt': ['erfurt', 'эрфурт'],
        'Mainz': ['mainz', 'майнц'],
        'Rostock': ['rostock', 'росток'],
        'Kassel': ['kassel', 'кассель'],
        'Hagen': ['hagen', 'хаген'],
        'Potsdam': ['potsdam', 'потсдам'],
        'Saarbrücken': ['saarbrucken', 'саарбрюккен'],
        'Hamm': ['hamm', 'хамм'],
        'Mülheim': ['mulheim', 'мюльхайм'],
        'Ludwigshafen': ['ludwigshafen', 'людвигсхафен'],
        'Leverkusen': ['leverkusen', 'леверкузен'],
        'Oldenburg': ['oldenburg', 'ольденбург'],
        'Neuss': ['neuss', 'нойс'],
        'Solingen': ['solingen', 'золинген'],
        'Heidelberg': ['heidelberg', 'хайдельберг'],
        'Darmstadt': ['darmstadt', 'дармштадт'],
        'Paderborn': ['paderborn', 'падерборн'],
        'Regensburg': ['regensburg', 'регенсбург'],
        'Würzburg': ['wurzburg', 'würzburg', 'вюрцбург'],
        'Ingolstadt': ['ingolstadt', 'ингольштадт'],
        'Heilbronn': ['heilbronn', 'хайльбронн'],
        'Ulm': ['ulm', 'ульм'],
        'Wolfsburg': ['wolfsburg', 'вольфсбург'],
        'Pforzheim': ['pforzheim', 'пфорцхайм'],
        'Göttingen': ['gottingen', 'göttingen', 'гёттинген'],
        'Recklinghausen': ['recklinghausen', 'реклингхаузен'],
        'Bottrop': ['bottrop', 'ботроп'],
        'Remscheid': ['remscheid', 'ремшайд'],
        'Bremerhaven': ['bremerhaven', 'бремерхафен'],
        'Bergisch Gladbach': ['bergisch gladbach', 'бергиш гладбах'],
        'Erlangen': ['erlangen', 'эрланген'],
        'Trier': ['trier', 'трир'],
        'Moers': ['moers', 'мёрс'],
        'Siegen': ['siegen', 'зиген'],
        'Hildesheim': ['hildesheim', 'хильдесхайм'],
        'Salzgitter': ['salzgitter', 'зальцгиттер'],
        'Cottbus': ['cottbus', 'котбус'],
        'Kaiserslautern': ['kaiserslautern', 'кайзерслаутерн'],
        'Witten': ['witten', 'виттен'],
        'Schwerin': ['schwerin', 'шверин'],
        'Esslingen': ['esslingen', 'эслинген'],
        'Gütersloh': ['gutersloh', 'гютерсло'],
        'Düren': ['duren', 'дюрен'],
        'Ratingen': ['ratingen', 'ратинген'],
        'Lünen': ['lunen', 'люнен'],
        'Hanau': ['hanau', 'ханау'],
        'Fürth': ['furth', 'фюрт'],
        'Kerpen': ['kerpen', 'керпен'],
        'Grevenbroich': ['grevenbroich', 'гревенбройх'],
        'Villingen-Schwenningen': ['villingen-schwenningen', 'виллинген-швеннинген'],
        'Rüsselsheim': ['russelsheim', 'рюссельсхайм'],
        'Marl': ['marl', 'марл'],
        'Norderstedt': ['norderstedt', 'нордерштедт'],
        'Konstanz': ['konstanz', 'констанц'],
        'Worms': ['worms', 'вормс'],
        'Dorsten': ['dorsten', 'дорстен'],
        'Lüdenscheid': ['ludenscheid', 'люденшайд'],
        'Wilhelmshaven': ['wilhelmshaven', 'вильгельмсхафен'],
        'Castrop-Rauxel': ['castrop-rauxel', 'кастроп-ракель'],
        'Gießen': ['giessen', 'гиссен'],
        'Detmold': ['detmold', 'детмольд'],
        'Plauen': ['plauen', 'плауэн'],
        'Neuwied': ['neuwied', 'нойвид'],
        'Marburg': ['marburg', 'марбург'],
        'Neubrandenburg': ['neubrandenburg', 'нойбранденбург'],
        'Gladbeck': ['gladbeck', 'гладбек'],
        'Velbert': ['velbert', 'фельберт'],
        'Viersen': ['viersen', 'фирзен'],
        'Troisdorf': ['troisdorf', 'тройсдорф']
    },
    'pl': {
        'Warsaw': ['warsaw', 'warszawa', 'варшава', 'varsovie'],
        'Krakow': ['krakow', 'cracow', 'краков', 'cracovie'],
        'Gdansk': ['gdansk', 'гданьск', 'danzig'],
        'Wroclaw': ['wroclaw', 'вроцлав', 'breslau'],
        'Poznan': ['poznan', 'познань', 'posen'],
        'Lodz': ['lodz', 'лодзь'],
        'Szczecin': ['szczecin', 'щецин', 'stettin'],
        'Bydgoszcz': ['bydgoszcz', 'быдгощ'],
        'Lublin': ['lublin', 'люблин'],
        'Katowice': ['katowice', 'катовице'],
        'Bialystok': ['bialystok', 'белосток'],
        'Gdynia': ['gdynia', 'гдыня'],
        'Czestochowa': ['czestochowa', 'ченстохова'],
        'Radom': ['radom', 'радом'],
        'Sosnowiec': ['sosnowiec', 'сосновец'],
        'Torun': ['torun', 'торунь'],
        'Kielce': ['kielce', 'кельце'],
        'Gliwice': ['gliwice', 'гливице'],
        'Zabrze': ['zabrze', 'забже'],
        'Bytom': ['bytom', 'бытом'],
        'Olsztyn': ['olsztyn', 'ольштын'],
        'Bielsko-Biala': ['bielsko-biala', 'бельско-бяла'],
        'Rzeszow': ['rzeszow', 'жешув'],
        'Rybnik': ['rybnik', 'рыбник'],
        'Ruda Slaska': ['ruda slaska', 'руда слёнска'],
        'Tychy': ['tychy', 'тыхи'],
        'Dabrowa Gornicza': ['dabrowa gornicza', 'домброва гурнича'],
        'Plock': ['plock', 'плоцк'],
        'Elblag': ['elblag', 'эльблонг'],
        'Walbrzych': ['walbrzych', 'валбжих'],
        'Tarnow': ['tarnow', 'тарнув'],
        'Chorzow': ['chorzow', 'хожув'],
        'Kalisz': ['kalisz', 'калиш'],
        'Koszalin': ['koszalin', 'кошалин'],
        'Legnica': ['legnica', 'легница'],
        'Grudziadz': ['grudziadz', 'грудзёндз'],
        'Slupsk': ['slupsk', 'слупск'],
        'Jaworzno': ['jaworzno', 'яворжно'],
        'Jastrzebie-Zdroj': ['jastrzebie-zdroj', 'ястжембе-здруй'],
        'Nowy Sacz': ['nowy sacz', 'новы сонч'],
        'Jelenia Gora': ['jelenia gora', 'еленя гура'],
        'Siedlce': ['siedlce', 'седльце'],
        'Myszkow': ['myszkow', 'мышкув'],
        'Konin': ['konin', 'конин'],
        'Piotrkow Trybunalski': ['piotrkow trybunalski', 'петркув трыбунальски'],
        'Inowroclaw': ['inowroclaw', 'иновроцлав'],
        'Lubin': ['lubin', 'любин'],
        'Ostrow Wielkopolski': ['ostrow wielkopolski', 'остров велькопольски'],
        'Gniezno': ['gniezno', 'гнезно'],
        'Stargard': ['stargard', 'старгард'],
        'Pulawy': ['pulawy', 'пулавы'],
        'Skierniewice': ['skierniewice', 'скерневице'],
        'Starachowice': ['starachowice', 'старахович'],
        'Zawiercie': ['zawiercie', 'заверце'],
        'Ostroleka': ['ostroleka', 'остролека'],
        'Zielona Gora': ['zielona gora', 'зелёна гура'],
        'Tczew': ['tczew', 'тчев'],
        'Tarnobrzeg': ['tarnobrzeg', 'тарнобжег'],
        'Chojnice': ['chojnice', 'хойнице'],
        'Zamość': ['zamosc', 'замосць'],
        'Lomza': ['lomza', 'ломжа'],
        'Leszno': ['leszno', 'лешно'],
        'Belchatow': ['belchatow', 'белхатув'],
        'Tomaszow Mazowiecki': ['tomaszow mazowiecki', 'томашув мазовецки'],
        'Przemysl': ['przemysl', 'пшемысль'],
        'Stalowa Wola': ['stalowa wola', 'сталёва воля'],
        'Malbork': ['malbork', 'мальборк'],
        'Wloclawek': ['wloclawek', 'влоцлавек'],
        'Swidnica': ['swidnica', 'свидница'],
        'Pila': ['pila', 'пила'],
        'Suwalki': ['suwalki', 'сувалки'],
        'Zory': ['zory', 'жоры'],
        'Opole': ['opole', 'ополе'],
        'Ostroda': ['ostroda', 'острода'],
        'Zywiec': ['zywiec', 'живец'],
        'Radomsko': ['radomsko', 'радомско'],
        'Bochnia': ['bochnia', 'бохня'],
        'Mielec': ['mielec', 'мелец'],
        'Biala Podlaska': ['biala podlaska', 'бяла подляска']
    },
    'gb': {
        'London': ['london', 'лондон', 'londres'],
        'Manchester': ['manchester', 'манчестер'],
        'Birmingham': ['birmingham', 'бирмингем'],
        'Leeds': ['leeds', 'лидс'],
        'Glasgow': ['glasgow', 'глазго'],
        'Liverpool': ['liverpool', 'ливерпуль'],
        'Newcastle': ['newcastle', 'ньюкасл'],
        'Sheffield': ['sheffield', 'шеффилд'],
        'Bristol': ['bristol', 'бристоль'],
        'Leicester': ['leicester', 'лестер'],
        'Edinburgh': ['edinburgh', 'эдинбург'],
        'Coventry': ['coventry', 'ковентри'],
        'Bradford': ['bradford', 'брэдфорд'],
        'Cardiff': ['cardiff', 'кардифф'],
        'Belfast': ['belfast', 'белфаст'],
        'Nottingham': ['nottingham', 'ноттингем'],
        'Kingston upon Hull': ['hull', 'хулл'],
        'Plymouth': ['plymouth', 'плимут'],
        'Stoke-on-Trent': ['stoke', 'сток'],
        'Wolverhampton': ['wolverhampton', 'вулверхэмптон'],
        'Derby': ['derby', 'дерби'],
        'Swansea': ['swansea', 'суонси'],
        'Southampton': ['southampton', 'саутгемптон'],
        'Salford': ['salford', 'солфорд'],
        'Aberdeen': ['aberdeen', 'абердин'],
        'Westminster': ['westminster', 'вестминстер'],
        'Portsmouth': ['portsmouth', 'портсмут'],
        'York': ['york', 'йорк'],
        'Peterborough': ['peterborough', 'питерборо'],
        'Dundee': ['dundee', 'данди'],
        'Lancaster': ['lancaster', 'ланкастер'],
        'Oxford': ['oxford', 'оксфорд'],
        'Newport': ['newport', 'ньюпорт'],
        'Preston': ['preston', 'престон'],
        'St Albans': ['st albans', 'сент-олбанс'],
        'Norwich': ['norwich', 'норидж'],
        'Chester': ['chester', 'честер'],
        'Dundee': ['dundee', 'данди'],
        'Exeter': ['exeter', 'эксетер'],
        'Gloucester': ['gloucester', 'глостер'],
        'Scunthorpe': ['scunthorpe', 'сканторп'],
        'Sunderland': ['sunderland', 'сандерленд'],
        'Ipswich': ['ipswich', 'ипсвич'],
        'Colchester': ['colchester', 'колчестер'],
        'Blackpool': ['blackpool', 'блэкпул'],
        'Bolton': ['bolton', 'болтон'],
        'Bournemouth': ['bournemouth', 'борнмут'],
        'Cambridge': ['cambridge', 'кембридж'],
        'Carlisle': ['carlisle', 'карлайл'],
        'Chester': ['chester', 'честер'],
        'Chichester': ['chichester', 'чичестер'],
        'Canterbury': ['canterbury', 'кентербери'],
        'Chelmsford': ['chelmsford', 'челмсфорд'],
        'Cheltenham': ['cheltenham', 'челтенхэм'],
        'Chesterfield': ['chesterfield', 'честерфилд'],
        'Darlington': ['darlington', 'дарлингтон'],
        'Doncaster': ['doncaster', 'донкастер'],
        'Durham': ['durham', 'дарем'],
        'Eastbourne': ['eastbourne', 'истборн'],
        'Guildford': ['guildford', 'гилфорд'],
        'Harrogate': ['harrogate', 'харрогейт'],
        'Hastings': ['hastings', 'гастингс'],
        'Hereford': ['hereford', 'херефорд'],
        'High Wycombe': ['high wycombe', 'хай викомб'],
        'Huddersfield': ['huddersfield', 'хаддерсфилд'],
        'Inverness': ['inverness', 'инвернесс'],
        'Lincoln': ['lincoln', 'линкольн'],
        'Luton': ['luton', 'лутон'],
        'Maidstone': ['maidstone', 'мейдстон'],
        'Middlesbrough': ['middlesbrough', 'мидлсбро'],
        'Milton Keynes': ['milton keynes', 'милтон кинс'],
        'Northampton': ['northampton', 'нортгемптон'],
        'Reading': ['reading', 'рединг'],
        'Rotherham': ['rotherham', 'ротерхэм'],
        'St Helens': ['st helens', 'сент-хеленс'],
        'Shrewsbury': ['shrewsbury', 'шрусбери'],
        'Slough': ['slough', 'слау'],
        'Stockport': ['stockport', 'стокпорт'],
        'Stockton-on-Tees': ['stockton', 'стоктон'],
        'Swindon': ['swindon', 'суиндон'],
        'Telford': ['telford', 'телфорд'],
        'Wakefield': ['wakefield', 'уэйкфилд'],
        'Warrington': ['warrington', 'уоррингтон'],
        'Watford': ['watford', 'уотфорд'],
        'Winchester': ['winchester', 'винчестер'],
        'Woking': ['woking', 'уокинг'],
        'Worcester': ['worcester', 'вустер'],
        'Worthing': ['worthing', 'уортинг'],
        'Wrexham': ['wrexham', 'рексхэм']
    },
    'nl': {
        'Amsterdam': ['amsterdam', 'амстердам'],
        'Rotterdam': ['rotterdam', 'роттердам'],
        'The Hague': ['the hague', 'hague', 'den haag', 'гаага'],
        'Utrecht': ['utrecht', 'утрехт'],
        'Eindhoven': ['eindhoven', 'эйндховен'],
        'Tilburg': ['tilburg', 'тилбург'],
        'Groningen': ['groningen', 'гронинген'],
        'Almere': ['almere', 'алмере'],
        'Breda': ['breda', 'бреда'],
        'Nijmegen': ['nijmegen', 'неймеген'],
        'Enschede': ['enschede', 'энсхеде'],
        'Haarlem': ['haarlem', 'харлем'],
        'Arnhem': ['arnhem', 'арнем'],
        'Zaanstad': ['zaanstad', 'занстад'],
        'Haarlemmermeer': ['haarlemmermeer', 'харлеммермер'],
        'Amersfoort': ['amersfoort', 'амерсфорт'],
        'Apeldoorn': ['apeldoorn', 'апелдорн'],
        'Zwolle': ['zwolle', 'цволле'],
        'Ede': ['ede', 'эде'],
        'Dordrecht': ['dordrecht', 'дордрехт'],
        'Leiden': ['leiden', 'лейден'],
        'Westland': ['westland', 'вестланд'],
        'Zoetermeer': ['zoetermeer', 'зутермер'],
        'Emmen': ['emmen', 'эммен'],
        'Delft': ['delft', 'делфт'],
        'Venlo': ['venlo', 'венло'],
        'Deventer': ['deventer', 'девентер'],
        'Leeuwarden': ['leeuwarden', 'леуварден'],
        'Alkmaar': ['alkmaar', 'алкмар'],
        'Hilversum': ['hilversum', 'хилверсум'],
        'Alphen aan den Rijn': ['alphen', 'алфен'],
        'Maastricht': ['maastricht', 'маастрихт'],
        'Purmerend': ['purmerend', 'пурмеренд'],
        'Roosendaal': ['roosendaal', 'розендал'],
        'Schiedam': ['schiedam', 'схидам'],
        'Spijkenisse': ['spijkenisse', 'спейкенисе'],
        'Vlaardingen': ['vlaardingen', 'влардинген'],
        'Almelo': ['almelo', 'алмело'],
        'Hoorn': ['hoorn', 'хорн'],
        'Oosterhout': ['oosterhout', 'остерхаут'],
        'Oss': ['oss', 'ос'],
        'Katwijk': ['katwijk', 'катвейк'],
        'Zeist': ['zeist', 'зейст'],
        'Nieuwegein': ['nieuwegein', 'нивегейн'],
        'Capelle aan den IJssel': ['capelle', 'капелле'],
        'Leidschendam-Voorburg': ['leidschendam', 'лейдшендам'],
        'Helmond': ['helmond', 'хелмонд'],
        'Hoofddorp': ['hoofddorp', 'хофддорп'],
        'Heerlen': ['heerlen', 'херлен'],
        'Gouda': ['gouda', 'гауда'],
        'Assen': ['assen', 'ассен'],
        'Middelburg': ['middelburg', 'миддельбург'],
        'Lelystad': ['lelystad', 'лелистад'],
        'Hengelo': ['hengelo', 'хенгело'],
        'Veenendaal': ['veenendaal', 'венендал'],
        'Den Helder': ['den helder', 'ден хелдер'],
        'Ridderkerk': ['ridderkerk', 'риддеркерк'],
        'Oldenzaal': ['oldenzaal', 'олденцал'],
        'Sittard-Geleen': ['sittard', 'ситтард'],
        'Stadskanaal': ['stadskanaal', 'стадсканал'],
        'Hardenberg': ['hardenberg', 'харденберг'],
        'Roermond': ['roermond', 'рурмонд'],
        'Doetinchem': ['doetinchem', 'дутинхем'],
        'Noordwijk': ['noordwijk', 'нордвейк'],
        'Barneveld': ['barneveld', 'барневелд'],
        'Weert': ['weert', 'верт'],
        'Bergen op Zoom': ['bergen op zoom', 'берген оп зом'],
        'Coevorden': ['coevorden', 'куворден'],
        'Heerhugowaard': ['heerhugowaard', 'херхуговард']
    },
    'fr': {
        'Paris': ['paris', 'париж', 'parys'],
        'Lyon': ['lyon', 'лион'],
        'Marseille': ['marseille', 'марсель'],
        'Toulouse': ['toulouse', 'тулуза'],
        'Nice': ['nice', 'ницца'],
        'Nantes': ['nantes', 'нант'],
        'Strasbourg': ['strasbourg', 'страсбург'],
        'Montpellier': ['montpellier', 'монпелье'],
        'Bordeaux': ['bordeaux', 'бордо'],
        'Lille': ['lille', 'лилль'],
        'Rennes': ['rennes', 'ренн'],
        'Reims': ['reims', 'реймс'],
        'Le Havre': ['le havre', 'ле авр'],
        'Saint-Étienne': ['saint-etienne', 'сент-этьен'],
        'Toulon': ['toulon', 'тулон'],
        'Angers': ['angers', 'анже'],
        'Grenoble': ['grenoble', 'гренобль'],
        'Dijon': ['dijon', 'дижон'],
        'Nîmes': ['nimes', 'ним'],
        'Aix-en-Provence': ['aix-en-provence', 'экс-ан-прованс'],
        'Saint-Quentin-en-Yvelines': ['saint-quentin', 'сен-кантен'],
        'Brest': ['brest', 'брест'],
        'Le Mans': ['le mans', 'ле ман'],
        'Amiens': ['amiens', 'амьен'],
        'Tours': ['tours', 'тур'],
        'Limoges': ['limoges', 'лимож'],
        'Clermont-Ferrand': ['clermont-ferrand', 'клермон-ферран'],
        'Villeurbanne': ['villeurbanne', 'вильербан'],
        'Besançon': ['besancon', 'безансон'],
        'Orléans': ['orleans', 'орлеан'],
        'Caen': ['caen', 'кан'],
        'Mulhouse': ['mulhouse', 'мюлуз'],
        'Rouen': ['rouen', 'руан'],
        'Nancy': ['nancy', 'нанси'],
        'Saint-Paul': ['saint-paul', 'сен-поль'],
        'Roubaix': ['roubaix', 'рубе'],
        'Tourcoing': ['tourcoing', 'туркуэн'],
        'Nanterre': ['nanterre', 'нантер'],
        'Avignon': ['avignon', 'авиньон'],
        'Créteil': ['creteil', 'кретей'],
        'Dunkerque': ['dunkerque', 'дюнкерк'],
        'Poitiers': ['poitiers', 'пуатье'],
        'Fort-de-France': ['fort-de-france', 'фор-де-франс'],
        'Courbevoie': ['courbevoie', 'курбевуа'],
        'Versailles': ['versailles', 'версаль'],
        'Colombes': ['colombes', 'коломб'],
        'Saint-Pierre': ['saint-pierre', 'сен-пьер'],
        'Aulnay-sous-Bois': ['aulnay-sous-bois', 'олне-су-буа'],
        'Asnières-sur-Seine': ['asnieres', 'аньер'],
        'Rueil-Malmaison': ['rueil-malmaison', 'рей-мальмезон'],
        'Aubervilliers': ['aubervilliers', 'обервилье'],
        'Champigny-sur-Marne': ['champigny', 'шампиньи'],
        'Saint-Maur-des-Fossés': ['saint-maur', 'сен-мор'],
        'Cannes': ['cannes', 'канн'],
        'Calais': ['calais', 'кале'],
        'Boulogne-Billancourt': ['boulogne-billancourt', 'булонь-бийанкур'],
        'Bourges': ['bourges', 'бурж'],
        'Saint-Nazaire': ['saint-nazaire', 'сен-назер'],
        'Valence': ['valence', 'валанс'],
        'Ajaccio': ['ajaccio', 'аяччо'],
        'Issy-les-Moulineaux': ['issy-les-moulineaux', 'иси-ле-мулино'],
        'Levallois-Perret': ['levallois-perret', 'леваллуа-перре'],
        'Quimper': ['quimper', 'кемпер'],
        'La Rochelle': ['la rochelle', 'ла рошель'],
        'Neuilly-sur-Seine': ['neuilly-sur-seine', 'нейи-сюр-сен'],
        'Niort': ['niort', 'ниор'],
        'Sarcelles': ['sarcelles', 'сарсель'],
        'Drancy': ['drancy', 'дранси'],
        'Antony': ['antony', 'антони'],
        'Villeneuve-d\'Ascq': ['villeneuve-d-ascq', 'вильнев-д-аск'],
        'Troyes': ['troyes', 'труа'],
        'Montauban': ['montauban', 'монтобан'],
        'Pessac': ['pessac', 'пессак'],
        'Ivry-sur-Seine': ['ivry-sur-seine', 'иври-сюр-сен'],
        'Cergy': ['cergy', 'сержи'],
        'Cayenne': ['cayenne', 'кайенна'],
        'Clichy': ['clichy', 'клиши'],
        'Saint-Ouen': ['saint-ouen', 'сент-уэн'],
        'Meaux': ['meaux', 'мо'],
        'Béziers': ['beziers', 'безье'],
        'Garges-lès-Gonesse': ['garges-les-gonesse', 'гарж-ле-гонесс'],
        'Saint-Brieuc': ['saint-brieuc', 'сен-бриё'],
        'Vannes': ['vannes', 'ванн'],
        'Fréjus': ['frejus', 'фрежюс'],
        'Évry': ['evry', 'эври'],
        'Cholet': ['cholet', 'шоле'],
        'Sartrouville': ['sartrouville', 'сартрувиль'],
        'Hyères': ['hyeres', 'йер'],
        'Mérignac': ['merignac', 'мериньяк'],
        'Belfort': ['belfort', 'бельфор'],
        'Chalon-sur-Saône': ['chalon-sur-saone', 'шалон-сюр-сон'],
        'Bayonne': ['bayonne', 'байонна'],
        'Arles': ['arles', 'арль'],
        'Vénissieux': ['venissieux', 'венисьё'],
        'Évreux': ['evreux', 'эврё'],
        'Corbeil-Essonnes': ['corbeil-essonnes', 'корбей-эссонн'],
        'Metz': ['metz', 'мец'],
        'Lens': ['lens', 'ланс'],
        'Pau': ['pau', 'по'],
        'Blois': ['blois', 'блуа'],
        'Cherbourg-Octeville': ['cherbourg', 'шербур'],
        'Laval': ['laval', 'лаваль'],
        'Albi': ['albi', 'альби'],
        'Angoulême': ['angouleme', 'ангулем'],
        'Bourg-en-Bresse': ['bourg-en-bresse', 'бур-ан-брес'],
        'Charleville-Mézières': ['charleville-mezieres', 'шарлевиль-мезьер'],
        'Châteauroux': ['chateauroux', 'шатору'],
        'Châlons-en-Champagne': ['chalons-en-champagne', 'шалон-ан-шампань'],
        'Colmar': ['colmar', 'кольмар'],
        'Gap': ['gap', 'гап'],
        'La Roche-sur-Yon': ['la roche-sur-yon', 'ла рош-сюр-йон'],
        'Mâcon': ['macon', 'макон'],
        'Montélimar': ['montelimar', 'монтелимар'],
        'Nevers': ['nevers', 'невер'],
        'Périgueux': ['perigueux', 'перигё'],
        'Privas': ['privas', 'прива'],
        'Saint-Lô': ['saint-lo', 'сен-ло'],
        'Tarbes': ['tarbes', 'тарб'],
        'Valence': ['valence', 'валанс'],
        'Vesoul': ['vesoul', 'везуль']
    },
    'at': {
        'Vienna': ['vienna', 'wien', 'вена'],
        'Salzburg': ['salzburg', 'зальцбург'],
        'Innsbruck': ['innsbruck', 'инсбрук'],
        'Graz': ['graz', 'грац'],
        'Linz': ['linz', 'линц'],
        'Klagenfurt': ['klagenfurt', 'клагенфурт'],
        'Villach': ['villach', 'филлах'],
        'Wels': ['wels', 'вельс'],
        'Sankt Pölten': ['sankt polten', 'санкт-пёльтен'],
        'Dornbirn': ['dornbirn', 'дорнбирн'],
        'Wiener Neustadt': ['wiener neustadt', 'винер нойштадт'],
        'Steyr': ['steyr', 'штайр'],
        'Feldkirch': ['feldkirch', 'фельдкирх'],
        'Bregenz': ['bregenz', 'брегенц'],
        'Leonding': ['leonding', 'леондинг'],
        'Klosterneuburg': ['klosterneuburg', 'клостернойбург'],
        'Baden': ['baden', 'баден'],
        'Wolfsberg': ['wolfsberg', 'вольфсберг'],
        'Leoben': ['leoben', 'леобен'],
        'Krems': ['krems', 'кремс'],
        'Traun': ['traun', 'траун'],
        'Amstetten': ['amstetten', 'амштеттен'],
        'Kapfenberg': ['kapfenberg', 'капфенберг'],
        'Mödling': ['modling', 'мёдлинг'],
        'Hallein': ['hallein', 'халляйн'],
        'Kufstein': ['kufstein', 'куфштайн'],
        'Traiskirchen': ['traiskirchen', 'трайскирхен'],
        'Schwechat': ['schwechat', 'швехат'],
        'Braunau am Inn': ['braunau', 'браунау'],
        'Stockerau': ['stockerau', 'штокерау'],
        'Saalfelden': ['saalfelden', 'зальфельден'],
        'Ansfelden': ['ansfelden', 'ансфельден'],
        'Tulln': ['tulln', 'тульн'],
        'Hohenems': ['hohenems', 'хоэнемс'],
        'Spittal an der Drau': ['spittal', 'шпитталь'],
        'Telfs': ['telfs', 'тельфс'],
        'Ternitz': ['ternitz', 'терниц'],
        'Perchtoldsdorf': ['perchtoldsdorf', 'перхтольдсдорф'],
        'Feldkirchen': ['feldkirchen', 'фельдкирхен'],
        'Bludenz': ['bludenz', 'блуденц'],
        'Bad Ischl': ['bad ischl', 'бад ишль'],
        'Schwaz': ['schwaz', 'швац'],
        'Hall in Tirol': ['hall in tirol', 'халль в тироле'],
        'Gmunden': ['gmunden', 'гмунден'],
        'Wörgl': ['worgl', 'вёргль'],
        'Enns': ['enns', 'эннс'],
        'Seekirchen am Wallersee': ['seekirchen', 'зекирхен'],
        'Sankt Veit an der Glan': ['sankt veit', 'санкт файт'],
        'Korneuburg': ['korneuburg', 'корнойбург']
    },
    'ch': {
        'Zurich': ['zurich', 'zürich', 'цюрих'],
        'Geneva': ['geneva', 'geneve', 'женева'],
        'Basel': ['basel', 'базель'],
        'Bern': ['bern', 'берн'],
        'Lausanne': ['lausanne', 'лозанна'],
        'Winterthur': ['winterthur', 'винтертур'],
        'Lucerne': ['lucerne', 'luzern', 'люцерн'],
        'St. Gallen': ['st gallen', 'санкт-галлен'],
        'Lugano': ['lugano', 'лугано'],
        'Biel': ['biel', 'биль'],
        'Thun': ['thun', 'тун'],
        'Köniz': ['koniz', 'кёниц'],
        'La Chaux-de-Fonds': ['la chaux-de-fonds', 'ла шо-де-фон'],
        'Schaffhausen': ['schaffhausen', 'шаффхаузен'],
        'Fribourg': ['fribourg', 'фрибур'],
        'Vernier': ['vernier', 'вернье'],
        'Chur': ['chur', 'кур'],
        'Neuchâtel': ['neuchatel', 'нёшатель'],
        'Uster': ['uster', 'устер'],
        'Sion': ['sion', 'сьон'],
        'Emmen': ['emmen', 'эммен'],
        'Zug': ['zug', 'цуг'],
        'Yverdon-les-Bains': ['yverdon', 'ивердон'],
        'Dübendorf': ['dubendorf', 'дюбендорф'],
        'Dietikon': ['dietikon', 'дитикон'],
        'Montreux': ['montreux', 'монтрё'],
        'Frauenfeld': ['frauenfeld', 'фрауэнфельд'],
        'Wetzikon': ['wetzikon', 'ветцикон'],
        'Baar': ['baar', 'бар'],
        'Meyrin': ['meyrin', 'мейрин'],
        'Riehen': ['riehen', 'риэн'],
        'Carouge': ['carouge', 'карух'],
        'Wädenswil': ['wadenswil', 'вёденсвиль'],
        'Allschwil': ['allschwil', 'альшвиль'],
        'Renens': ['renens', 'ренан'],
        'Kloten': ['kloten', 'клотен'],
        'Nyon': ['nyon', 'ньон'],
        'Bulle': ['bulle', 'буль'],
        'Kreuzlingen': ['kreuzlingen', 'кройцлинген'],
        'Pully': ['pully', 'пюлли'],
        'Ostermundigen': ['ostermundigen', 'остермундиген'],
        'Steffisburg': ['steffisburg', 'штеффисбург'],
        'Wil': ['wil', 'виль'],
        'La Tour-de-Peilz': ['la tour-de-peilz', 'ла тур-де-пей'],
        'Bellinzona': ['bellinzona', 'беллинцона'],
        'Bülach': ['bulach', 'бюлах'],
        'Rapperswil-Jona': ['rapperswil', 'рапперсвиль'],
        'Burgdorf': ['burgdorf', 'бургдорф'],
        'Sierre': ['sierre', 'сьер'],
        'Langenthal': ['langenthal', 'лангенталь'],
        'Prilly': ['prilly', 'прильи'],
        'Grenchen': ['grenchen', 'гренхен'],
        'Morges': ['morges', 'морж'],
        'Olten': ['olten', 'ольтен'],
        'Wettingen': ['wettingen', 'веттинген'],
        'Onex': ['onex', 'онекс'],
        'Lancy': ['lancy', 'ланси'],
        'Volketswil': ['volketswil', 'фолькетсвиль'],
        'Horgen': ['horgen', 'хорген'],
        'Vevey': ['vevey', 'веве'],
        'Oftringen': ['oftringen', 'офтринген'],
        'Martigny': ['martigny', 'мартиньи'],
        'Adliswil': ['adliswil', 'адлисвиль'],
        'Münsingen': ['munsingen', 'мюнзинген'],
        'Zollikofen': ['zollikofen', 'цолликофен'],
        'Liestal': ['liestal', 'листаль'],
        'Schlieren': ['schlieren', 'шлирен'],
        'Monthey': ['monthey', 'монте'],
        'Solothurn': ['solothurn', 'золотурн'],
        'Gossau': ['gossau', 'госсау'],
        'Herisau': ['herisau', 'херизау']
    },
    'be': {
        'Brussels': ['brussels', 'bruxelles', 'brussel', 'брюссель'],
        'Antwerp': ['antwerp', 'antwerpen', 'anvers', 'антверпен'],
        'Ghent': ['ghent', 'gent', 'gand', 'гент'],
        'Charleroi': ['charleroi', 'шарлеруа'],
        'Liège': ['liege', 'luik', 'льеж'],
        'Bruges': ['bruges', 'brugge', 'брюгге'],
        'Namur': ['namur', 'namen', 'намюр'],
        'Leuven': ['leuven', 'louvain', 'лёвен'],
        'Mons': ['mons', 'bergen', 'монс'],
        'Aalst': ['aalst', 'alost', 'алст'],
        'Mechelen': ['mechelen', 'malines', 'мехелен'],
        'La Louvière': ['la louviere', 'ла лувьер'],
        'Kortrijk': ['kortrijk', 'courtrai', 'кортрейк'],
        'Hasselt': ['hasselt', 'хасселт'],
        'Sint-Niklaas': ['sint-niklaas', 'saint-nicolas', 'синт-никлас'],
        'Ostend': ['ostend', 'oostende', 'ostende', 'остенде'],
        'Tournai': ['tournai', 'doornik', 'турне'],
        'Genk': ['genk', 'генк'],
        'Seraing': ['seraing', 'серэн'],
        'Roeselare': ['roeselare', 'roulers', 'руселаре'],
        'Mouscron': ['mouscron', 'moeskroen', 'мускрон'],
        'Verviers': ['verviers', 'верьвье'],
        'Dendermonde': ['dendermonde', 'termonde', 'дендермонде'],
        'Beringen': ['beringen', 'берінген'],
        'Turnhout': ['turnhout', 'турнхаут'],
        'Vilvoorde': ['vilvoorde', 'vilvorde', 'вилворде'],
        'Lokeren': ['lokeren', 'локерен'],
        'Sint-Truiden': ['sint-truiden', 'saint-trond', 'синт-трёйден'],
        'Brasschaat': ['brasschaat', 'брасхат'],
        'Tienen': ['tienen', 'tirlemont', 'тинен'],
        'Maasmechelen': ['maasmechelen', 'масмехелен'],
        'Waregem': ['waregem', 'варегем'],
        'Lommel': ['lommel', 'ломмел'],
        'Mol': ['mol', 'моль'],
        'Mortsel': ['mortsel', 'морцел'],
        'Binche': ['binche', 'бинш'],
        'Ath': ['ath', 'ат'],
        'Ninove': ['ninove', 'нинове'],
        'Geel': ['geel', 'геель'],
        'Ieper': ['ieper', 'ypres', 'ипр'],
        'Deinze': ['deinze', 'дейнзе'],
        'Brecht': ['brecht', 'брехт'],
        'Tielt': ['tielt', 'тилт'],
        'Tongeren': ['tongeren', 'tongres', 'тонгерен'],
        'Poperinge': ['poperinge', 'поперинге'],
        'Halle': ['halle', 'hal', 'халле'],
        'Wavre': ['wavre', 'waver', 'вавр'],
        'Soignies': ['soignies', 'zinnik', 'суаньи'],
        'Châtelet': ['chatelet', 'шатле'],
        'Oudenaarde': ['oudenaarde', 'audenarde', 'ауденарде'],
        'Herentals': ['herentals', 'херенталс'],
        'Aarschot': ['aarschot', 'аршот'],
        'Nivelles': ['nivelles', 'nijvel', 'нивель'],
        'Fleurus': ['fleurus', 'флёрюс'],
        'Lessines': ['lessines', 'lessen', 'лессин'],
        'Gembloux': ['gembloux', 'гемблу'],
        'Huy': ['huy', 'hoei', 'юи'],
        'Diest': ['diest', 'дист'],
        'Zottegem': ['zottegem', 'зоттегем'],
        'Lier': ['lier', 'lierre', 'лир'],
        'Geraardsbergen': ['geraardsbergen', 'grammont', 'герардсберген'],
        'Boom': ['boom', 'бом'],
        'Blankenberge': ['blankenberge', 'бланкенберге']
    },
    'dk': {
        'Copenhagen': ['copenhagen', 'kobenhavn', 'københavn', 'копенгаген'],
        'Aarhus': ['aarhus', 'орхус'],
        'Odense': ['odense', 'оденсе'],
        'Aalborg': ['aalborg', 'ольборг'],
        'Esbjerg': ['esbjerg', 'эсбьерг'],
        'Randers': ['randers', 'раннерс'],
        'Kolding': ['kolding', 'колдинг'],
        'Horsens': ['horsens', 'хорсенс'],
        'Vejle': ['vejle', 'вайле'],
        'Roskilde': ['roskilde', 'роскилле'],
        'Herning': ['herning', 'хернинг'],
        'Helsingør': ['helsingor', 'эльсинор'],
        'Silkeborg': ['silkeborg', 'силькеборг'],
        'Næstved': ['naestved', 'нествед'],
        'Fredericia': ['fredericia', 'фредерисия'],
        'Viborg': ['viborg', 'виборг'],
        'Køge': ['koge', 'кёге'],
        'Holstebro': ['holstebro', 'хольстебро'],
        'Taastrup': ['taastrup', 'тоструп'],
        'Slagelse': ['slagelse', 'слагельсе'],
        'Hillerød': ['hillerod', 'хиллерёд'],
        'Sønderborg': ['sonderborg', 'сённерборг'],
        'Svendborg': ['svendborg', 'свенборг'],
        'Hjørring': ['hjorring', 'йёрринг'],
        'Frederiksberg': ['frederiksberg', 'фредериксберг'],
        'Nørresundby': ['norresundby', 'нёрресуннбю'],
        'Ringsted': ['ringsted', 'рингстед'],
        'Ølstykke-Stenløse': ['olstykke-stenlose', 'ёльстюкке-стенлёсе'],
        'Skive': ['skive', 'скиве'],
        'Korsør': ['korsor', 'корсёр'],
        'Holbæk': ['holbaek', 'хольбек'],
        'Tilst': ['tilst', 'тильст'],
        'Farum': ['farum', 'фарум'],
        'Hørsholm': ['horsholm', 'хёрсхольм'],
        'Brønby': ['bronby', 'брёнбю'],
        'Ishøj': ['ishoj', 'ишёй'],
        'Charlottenlund': ['charlottenlund', 'шарлоттенлунн'],
        'Birkerød': ['birkerod', 'биркерёд'],
        'Værløse': ['varlose', 'варлёсе'],
        'Hedehusene': ['hedehusene', 'хедехусене'],
        'Albertslund': ['albertslund', 'альбертслунн'],
        'Glostrup': ['glostrup', 'глоструп'],
        'Hvidovre': ['hvidovre', 'видовре'],
        'Brøndby': ['brondby', 'брённбю'],
        'Vallensbæk': ['vallensbaek', 'валленсбек'],
        'Ballerup': ['ballerup', 'баллеруп'],
        'Gentofte': ['gentofte', 'гентофте'],
        'Lyngby-Taarbæk': ['lyngby-taarbaek', 'люнгбю-торбек'],
        'Rudersdal': ['rudersdal', 'рудерсдаль'],
        'Furesø': ['fureso', 'фуресё'],
        'Egedal': ['egedal', 'эгедаль'],
        'Fredensborg': ['fredensborg', 'фреденсборг'],
        'Allerød': ['allerod', 'аллерёд'],
        'Helsingør': ['helsingor', 'эльсинор'],
        'Gilleleje': ['gilleleje', 'гиллелейе'],
        'Humlebæk': ['humlebaek', 'хумлебек'],
        'Espergærde': ['espergaerde', 'эсперьгерде'],
        'Frederiksværk': ['frederiksvaerk', 'фредериксверк'],
        'Hundested': ['hundested', 'хуннестед'],
        'Jægerspris': ['jaegerspris', 'йегерсприс'],
        'Ølsted': ['olsted', 'ёльстед']
    },
    'se': {
        'Stockholm': ['stockholm', 'стокгольм'],
        'Gothenburg': ['gothenburg', 'goteborg', 'göteborg', 'гётеборг'],
        'Malmö': ['malmo', 'malmoe', 'мальмё'],
        'Uppsala': ['uppsala', 'упсала'],
        'Västerås': ['vasteras', 'вестерос'],
        'Örebro': ['orebro', 'ёребру'],
        'Linköping': ['linkoping', 'линчёпинг'],
        'Helsingborg': ['helsingborg', 'хельсингборг'],
        'Jönköping': ['jonkoping', 'йёнчёпинг'],
        'Norrköping': ['norrkoping', 'норрчёпинг'],
        'Lund': ['lund', 'лунд'],
        'Umeå': ['umea', 'умео'],
        'Gävle': ['gavle', 'евле'],
        'Borås': ['boras', 'борос'],
        'Eskilstuna': ['eskilstuna', 'эскильстуна'],
        'Södertälje': ['sodertalje', 'сёдертелье'],
        'Karlstad': ['karlstad', 'карльстад'],
        'Täby': ['taby', 'тебю'],
        'Växjö': ['vaxjo', 'векшё'],
        'Halmstad': ['halmstad', 'хальмстад'],
        'Sundsvall': ['sundsvall', 'суннсваль'],
        'Luleå': ['lulea', 'лулео'],
        'Trollhättan': ['trollhattan', 'тролльхеттан'],
        'Östersund': ['ostersund', 'ёстерсунд'],
        'Borlänge': ['borlange', 'борленге'],
        'Falun': ['falun', 'фалун'],
        'Tumba': ['tumba', 'тумба'],
        'Kristianstad': ['kristianstad', 'кристианстад'],
        'Karlskrona': ['karlskrona', 'карльскруна'],
        'Skövde': ['skovde', 'шёвде'],
        'Uddevalla': ['uddevalla', 'уддевалла'],
        'Motala': ['motala', 'мутала'],
        'Landskrona': ['landskrona', 'ландскруна'],
        'Trelleborg': ['trelleborg', 'треллеборг'],
        'Kalmar': ['kalmar', 'кальмар'],
        'Kiruna': ['kiruna', 'кируна'],
        'Örnsköldsvik': ['ornskoldsvik', 'ёрншёльдсвик'],
        'Karlskoga': ['karlskoga', 'карльскуга'],
        'Skellefteå': ['skelleftea', 'шеллефтео'],
        'Sandviken': ['sandviken', 'сандвикен'],
        'Piteå': ['pitea', 'питео'],
        'Boden': ['boden', 'буден'],
        'Ängelholm': ['angelholm', 'энгельхольм'],
        'Falkenberg': ['falkenberg', 'фалькенберг'],
        'Lidköping': ['lidkoping', 'лидчёпинг'],
        'Nyköping': ['nykoping', 'нючёпинг'],
        'Arvika': ['arvika', 'арвика'],
        'Lerum': ['lerum', 'лерум'],
        'Sandviken': ['sandviken', 'сандвикен'],
        'Tibro': ['tibro', 'тибру'],
        'Mora': ['mora', 'мура'],
        'Kumla': ['kumla', 'кумла'],
        'Tranås': ['tranas', 'тронос'],
        'Mariestad': ['mariestad', 'мариестад'],
        'Bollnäs': ['bollnas', 'больнес'],
        'Oxelösund': ['oxelosund', 'оксельёсунд'],
        'Sandviken': ['sandviken', 'сандвикен'],
        'Vetlanda': ['vetlanda', 'ветланда'],
        'Vimmerby': ['vimmerby', 'виммербю'],
        'Katrineholm': ['katrineholm', 'катринехольм'],
        'Älmhult': ['almhult', 'эльмхульт'],
        'Ystad': ['ystad', 'истад'],
        'Höganäs': ['hoganas', 'хёганес'],
        'Enköping': ['enkoping', 'энчёпинг'],
        'Alingsås': ['alingsas', 'алингсос'],
        'Staffanstorp': ['staffanstorp', 'стаффансторп'],
        'Kungsbacka': ['kungsbacka', 'кунгсбакка'],
        'Varberg': ['varberg', 'варберг'],
        'Laholm': ['laholm', 'лахольм'],
        'Båstad': ['bastad', 'бостад'],
        'Svalöv': ['svalov', 'свалёв'],
        'Bjuv': ['bjuv', 'бьюв'],
        'Kävlinge': ['kavlinge', 'кевлинге'],
        'Lomma': ['lomma', 'ломма'],
        'Burlöv': ['burlov', 'бурлёв'],
        'Vellinge': ['vellinge', 'веллинге'],
        'Skurup': ['skurup', 'скуруп'],
        'Sjöbo': ['sjobo', 'шёбу'],
        'Tomelilla': ['tomelilla', 'томелилла'],
        'Simrishamn': ['simrishamn', 'симришамн'],
        'Österlen': ['osterlen', 'ёстерлен'],
        'Hässleholm': ['hassleholm', 'хесслехольм'],
        'Osby': ['osby', 'осбю'],
        'Älmhult': ['almhult', 'эльмхульт'],
        'Markaryd': ['markaryd', 'маркарюд'],
        'Växjö': ['vaxjo', 'векшё'],
        'Alvesta': ['alvesta', 'альвеста'],
        'Ljungby': ['ljungby', 'льунгбю'],
        'Tingsryd': ['tingsryd', 'тингсрюд'],
        'Uppvidinge': ['uppvidinge', 'уппвидинге'],
        'Lessebo': ['lessebo', 'лессебу'],
        'Emmaboda': ['emmaboda', 'эммабуда'],
        'Kalmar': ['kalmar', 'кальмар'],
        'Nybro': ['nybro', 'нюбру'],
        'Oskarshamn': ['oskarshamn', 'оскаршамн'],
        'Västervik': ['vastervik', 'вестервик'],
        'Vimmerby': ['vimmerby', 'виммербю'],
        'Hultsfred': ['hultsfred', 'хультсфред'],
        'Högsby': ['hogsby', 'хёгсбю'],
        'Torsås': ['torsas', 'торсос'],
        'Mörbylånga': ['morbylanga', 'мёрбюлонга'],
        'Borgholm': ['borgholm', 'боргхольм']
    },
    'no': {
        'Oslo': ['oslo', 'осло'],
        'Bergen': ['bergen', 'берген'],
        'Trondheim': ['trondheim', 'тронхейм'],
        'Stavanger': ['stavanger', 'ставангер'],
        'Bærum': ['baerum', 'берум'],
        'Kristiansand': ['kristiansand', 'кристиансанн'],
        'Fredrikstad': ['fredrikstad', 'фредрикстад'],
        'Sandnes': ['sandnes', 'саннес'],
        'Tromsø': ['tromso', 'тромсё'],
        'Sarpsborg': ['sarpsborg', 'сарпсборг'],
        'Skien': ['skien', 'шиен'],
        'Ålesund': ['alesund', 'олесунн'],
        'Sandefjord': ['sandefjord', 'саннефьорд'],
        'Haugesund': ['haugesund', 'хаугесунн'],
        'Tønsberg': ['tonsberg', 'тёнсберг'],
        'Moss': ['moss', 'мосс'],
        'Drammen': ['drammen', 'драммен'],
        'Asker': ['asker', 'аскер'],
        'Lillestrøm': ['lillestrom', 'лиллестрём'],
        'Ullensaker': ['ullensaker', 'улленсакер'],
        'Lørenskog': ['lorenskog', 'лёренског'],
        'Oppegård': ['oppegard', 'оппегорд'],
        'Nordre Follo': ['nordre follo', 'нордре фолло'],
        'Ås': ['as', 'ос'],
        'Frogn': ['frogn', 'фрогн'],
        'Nesodden': ['nesodden', 'несодден'],
        'Vestby': ['vestby', 'вестбю'],
        'Eidsvoll': ['eidsvoll', 'эйдсволль'],
        'Nannestad': ['nannestad', 'наннестад'],
        'Hurdal': ['hurdal', 'хурдаль'],
        'Gjerdrum': ['gjerdrum', 'йердрум'],
        'Rælingen': ['ralingen', 'релинген'],
        'Enebakk': ['enebakk', 'энебакк'],
        'Aurskog-Høland': ['aurskog-holand', 'аурског-хёланд'],
        'Nes': ['nes', 'нес'],
        'Sørum': ['sorum', 'сёрум'],
        'Fet': ['fet', 'фет'],
        'Skedsmo': ['skedsmo', 'скедсму'],
        'Nittedal': ['nittedal', 'ниттедаль'],
        'Lunner': ['lunner', 'луннер'],
        'Gran': ['gran', 'гран'],
        'Jevnaker': ['jevnaker', 'йевнакер'],
        'Hole': ['hole', 'холе'],
        'Ringerike': ['ringerike', 'рингерике'],
        'Modum': ['modum', 'модум'],
        'Krødsherad': ['krodsherad', 'крёдшерад'],
        'Flå': ['fla', 'фло'],
        'Nesbyen': ['nesbyen', 'несбюен'],
        'Gol': ['gol', 'голь'],
        'Hemsedal': ['hemsedal', 'хемседаль'],
        'Ål': ['al', 'оль'],
        'Hol': ['hol', 'холь'],
        'Sigdal': ['sigdal', 'сигдаль'],
        'Flesberg': ['flesberg', 'флесберг'],
        'Rollag': ['rollag', 'роллаг'],
        'Nore og Uvdal': ['nore og uvdal', 'норе ог увдаль'],
        'Kongsberg': ['kongsberg', 'конгсберг'],
        'Horten': ['horten', 'хортен'],
        'Holmestrand': ['holmestrand', 'хольместранд'],
        'Re': ['re', 'ре'],
        'Lier': ['lier', 'лиер'],
        'Øvre Eiker': ['ovre eiker', 'ёвре эйкер'],
        'Nedre Eiker': ['nedre eiker', 'недре эйкер'],
        'Røyken': ['royken', 'рёйкен'],
        'Hurum': ['hurum', 'хурум'],
        'Sande': ['sande', 'санде'],
        'Hof': ['hof', 'хоф'],
        'Larvik': ['larvik', 'ларвик'],
        'Porsgrunn': ['porsgrunn', 'порсгрунн'],
        'Bamble': ['bamble', 'бамбле'],
        'Kragerø': ['kragero', 'крагерё'],
        'Drangedal': ['drangedal', 'дрангедаль'],
        'Nome': ['nome', 'номе'],
        'Bø': ['bo', 'бё'],
        'Sauherad': ['sauherad', 'саухерад'],
        'Tinn': ['tinn', 'тинн'],
        'Hjartdal': ['hjartdal', 'йартдаль'],
        'Seljord': ['seljord', 'сельйорд'],
        'Kviteseid': ['kviteseid', 'квитесейд'],
        'Nissedal': ['nissedal', 'нисседаль'],
        'Fyresdal': ['fyresdal', 'фюресдаль'],
        'Tokke': ['tokke', 'токке'],
        'Vinje': ['vinje', 'винье'],
        'Siljan': ['siljan', 'сильян'],
        'Notodden': ['notodden', 'нотодден'],
        'Eidfjord': ['eidfjord', 'эйдфьорд'],
        'Ullensvang': ['ullensvang', 'улленсванг'],
        'Granvin': ['granvin', 'гранвин'],
        'Voss': ['voss', 'восс'],
        'Kvam': ['kvam', 'квам'],
        'Fusa': ['fusa', 'фуса'],
        'Samnanger': ['samnanger', 'самнангер'],
        'Os': ['os', 'ос'],
        'Austevoll': ['austevoll', 'аустеволль'],
        'Sund': ['sund', 'сунн'],
        'Fjell': ['fjell', 'фьелль'],
        'Askøy': ['askoy', 'аскёй'],
        'Vaksdal': ['vaksdal', 'ваксдаль'],
        'Modalen': ['modalen', 'модален'],
        'Osterøy': ['osteroy', 'остерёй'],
        'Meland': ['meland', 'меланн'],
        'Øygarden': ['oygarden', 'ёйгарден'],
        'Radøy': ['radoy', 'радёй'],
        'Lindås': ['lindas', 'линдос'],
        'Austrheim': ['austrheim', 'аустрхейм'],
        'Fedje': ['fedje', 'федье'],
        'Masfjorden': ['masfjorden', 'масфьорден']
    },
    'cz': {
        'Prague': ['prague', 'praha', 'прага'],
        'Brno': ['brno', 'брно'],
        'Ostrava': ['ostrava', 'острава'],
        'Plzen': ['plzen', 'pilsen', 'пльзень'],
        'Liberec': ['liberec', 'либерец'],
        'Olomouc': ['olomouc', 'оломоуц'],
        'Ústí nad Labem': ['usti nad labem', 'усти-над-лабем'],
        'České Budějovice': ['ceske budejovice', 'ческе-будеёвице'],
        'Hradec Králové': ['hradec kralove', 'градец-кралове'],
        'Pardubice': ['pardubice', 'пардубице'],
        'Zlín': ['zlin', 'злин'],
        'Havířov': ['havirov', 'гавиржов'],
        'Kladno': ['kladno', 'кладно'],
        'Most': ['most', 'мост'],
        'Opava': ['opava', 'опава'],
        'Frýdek-Místek': ['frydek-mistek', 'фридек-мистек'],
        'Karviná': ['karvina', 'карвина'],
        'Jihlava': ['jihlava', 'йиглава'],
        'Teplice': ['teplice', 'теплице'],
        'Děčín': ['decin', 'дечин'],
        'Karlovy Vary': ['karlovy vary', 'карловы-вары'],
        'Jablonec nad Nisou': ['jablonec nad nisou', 'яблонец-над-нисоу'],
        'Mladá Boleslav': ['mlada boleslav', 'млада-болеслав'],
        'Prostějov': ['prostejov', 'простеёв'],
        'Přerov': ['prerov', 'пршеров'],
        'Česká Lípa': ['ceska lipa', 'ческа-липа'],
        'Třebíč': ['trebic', 'тршебич'],
        'Tabor': ['tabor', 'табор'],
        'Znojmo': ['znojmo', 'зноймо'],
        'Kolín': ['kolin', 'колин'],
        'Písek': ['pisek', 'писек'],
        'Třinec': ['trinec', 'тршинец'],
        'Cheb': ['cheb', 'хеб'],
        'Trutnov': ['trutnov', 'трутнов'],
        'Chomutov': ['chomutov', 'хомутов'],
        'Klášterec nad Ohří': ['klasterec nad ohri', 'кластерец-над-огржи'],
        'Uherské Hradiště': ['uherske hradiste', 'угерске-градиште'],
        'Kutná Hora': ['kutna hora', 'кутна-гора'],
        'Hranice': ['hranice', 'границе'],
        'Břeclav': ['breclav', 'бржецлав'],
        'Krnov': ['krnov', 'крнов'],
        'Sokolov': ['sokolov', 'соколов'],
        'Hodonín': ['hodonin', 'годонин'],
        'Český Těšín': ['cesky tesin', 'ческий-тешин'],
        'Strakonice': ['strakonice', 'страконице'],
        'Valašské Meziříčí': ['valasske mezirici', 'валашске-мезиржичи'],
        'Litoměřice': ['litomerice', 'литомержице'],
        'Vsetín': ['vsetin', 'всетин'],
        'Otrokovice': ['otrokovice', 'отроковице'],
        'Pelhřimov': ['pelhrimov', 'пельгржимов'],
        'Šumperk': ['sumperk', 'шумперк'],
        'Nový Jičín': ['novy jicin', 'новы-йичин'],
        'Benešov': ['benesov', 'бенешов'],
        'Kroměříž': ['kromeriz', 'кромержиж'],
        'Dvůr Králové nad Labem': ['dvur kralove nad labem', 'двур-кралове-над-лабем'],
        'Žďár nad Sázavou': ['zdar nad sazavou', 'ждар-над-сазавоу'],
        'Jičín': ['jicin', 'йичин'],
        'Beroun': ['beroun', 'бероун'],
        'Blansko': ['blansko', 'бланско'],
        'Náchod': ['nachod', 'наход'],
        'Týn nad Vltavou': ['tyn nad vltavou', 'тын-над-влтавоу'],
        'Česká Třebová': ['ceska trebova', 'ческа-тршебова'],
        'Přelouč': ['prelouc', 'пршелоуч'],
        'Čáslav': ['caslav', 'часлав'],
        'Nymburk': ['nymburk', 'нымбурк'],
        'Roudnice nad Labem': ['roudnice nad labem', 'роуднице-над-лабем'],
        'Mělník': ['melnik', 'мельник'],
        'Neratovice': ['neratovice', 'нератовице'],
        'Kralupy nad Vltavou': ['kralupy nad vltavou', 'кралупы-над-влтавоу'],
        'Slaný': ['slany', 'сланы'],
        'Rakovník': ['rakovnik', 'раковник'],
        'Litvínov': ['litvinov', 'литвинов'],
        'Bílina': ['bilina', 'билина'],
        'Louny': ['louny', 'лоуны'],
        'Žatec': ['zatec', 'жатец'],
        'Kadaň': ['kadan', 'кадань'],
        'Aš': ['as', 'аш'],
        'Mariánské Lázně': ['marianske lazne', 'марианске-лазне'],
        'Ostrov': ['ostrov', 'остров'],
        'Jirkov': ['jirkov', 'йирков']
    },
    'sk': {
        'Bratislava': ['bratislava', 'братислава'],
        'Košice': ['kosice', 'кошице'],
        'Prešov': ['presov', 'прешов'],
        'Žilina': ['zilina', 'жилина'],
        'Banská Bystrica': ['banska bystrica', 'банска-быстрица'],
        'Nitra': ['nitra', 'нитра'],
        'Trnava': ['trnava', 'трнава'],
        'Martin': ['martin', 'мартин'],
        'Trenčín': ['trencin', 'тренчин'],
        'Poprad': ['poprad', 'попрад'],
        'Prievidza': ['prievidza', 'приевидза'],
        'Zvolen': ['zvolen', 'зволен'],
        'Považská Bystrica': ['povazska bystrica', 'поважска-быстрица'],
        'Michalovce': ['michalovce', 'михаловце'],
        'Spišská Nová Ves': ['spisska nova ves', 'спишска-нова-вес'],
        'Komárno': ['komarno', 'комарно'],
        'Levice': ['levice', 'левице'],
        'Humenné': ['humenne', 'гуменне'],
        'Bardejov': ['bardejov', 'бардеёв'],
        'Liptovský Mikuláš': ['liptovsky mikulas', 'липтовски-микулаш'],
        'Ružomberok': ['ruzomberok', 'ружомберок'],
        'Dolný Kubín': ['dolny kubin', 'долны-кубин'],
        'Námestovo': ['namestovo', 'наместово'],
        'Tvrdošín': ['tvrdosin', 'твردошин'],
        'Čadca': ['cadca', 'чадца'],
        'Kysucké Nové Mesto': ['kysucke nove mesto', 'кисуцке-нове-место'],
        'Turzovka': ['turzovka', 'турзовка'],
        'Rajec': ['rajec', 'райец'],
        'Bytča': ['bytca', 'бытча'],
        'Žiar nad Hronom': ['ziar nad hronom', 'жиар-над-гроном'],
        'Handlová': ['handlova', 'гандлова'],
        'Bojnice': ['bojnice', 'бойнице'],
        'Partizánske': ['partizanske', 'партизанске'],
        'Bánovce nad Bebravou': ['banovce nad bebravou', 'бановце-над-бебравоу'],
        'Nové Mesto nad Váhom': ['nove mesto nad vahom', 'нове-место-над-вагом'],
        'Myšľany': ['myslany', 'мышляны'],
        'Senica': ['senica', 'сенница'],
        'Malacky': ['malacky', 'малацки'],
        'Skalica': ['skalica', 'скалица'],
        'Holíč': ['holic', 'голич'],
        'Gbely': ['gbely', 'гбелы'],
        'Dunajská Streda': ['dunajska streda', 'дунайска-среда'],
        'Veľký Meder': ['velky meder', 'велькы-медер'],
        'Šaľa': ['sala', 'шаля'],
        'Galanta': ['galanta', 'галанта'],
        'Sereď': ['sered', 'середь'],
        'Hlohovec': ['hlohovec', 'глоговец'],
        'Piešťany': ['piestany', 'пиештяны'],
        'Vrbové': ['vrbove', 'врбове'],
        'Nové Zámky': ['nove zamky', 'нове-замкы'],
        'Štúrovo': ['sturovo', 'штурово'],
        'Želiezovce': ['zeliezovce', 'желиезовце'],
        'Šurany': ['surany', 'шураны'],
        'Topoľčany': ['topolcany', 'топольчаны'],
        'Zlaté Moravce': ['zlate moravce', 'злате-моравце'],
        'Vráble': ['vruble', 'врубле'],
        'Šahy': ['sahy', 'шагы'],
        'Fiľakovo': ['filakovo', 'филяково'],
        'Lučenec': ['lucenec', 'лученец'],
        'Poltár': ['poltar', 'полтар'],
        'Veľký Krtíš': ['velky krtis', 'велькы-кртиш'],
        'Rimavská Sobota': ['rimavska sobota', 'римавска-собота'],
        'Revúca': ['revuca', 'ревуца'],
        'Tisovec': ['tisovec', 'тисовец'],
        'Brezno': ['brezno', 'брезно'],
        'Detva': ['detva', 'детва'],
        'Krupina': ['krupina', 'крупина'],
        'Žarnovica': ['zarnovica', 'жарновица'],
        'Kremnica': ['kremnica', 'кремница'],
        'Žarnovica': ['zarnovica', 'жарновица'],
        'Nová Baňa': ['nova bana', 'нова-баня'],
        'Trenčianske Teplice': ['trencianske teplice', 'тренчианске-теплице'],
        'Púchov': ['puchov', 'пухов'],
        'Ilava': ['ilava', 'илава'],
        'Dubnica nad Váhom': ['dubnica nad vahom', 'дубница-над-вагом'],
        'Myjava': ['myjava', 'мыява'],
        'Stará Turá': ['stara tura', 'стара-тура'],
        'Brezová pod Bradlom': ['brezova pod bradlom', 'брезова-под-брадлом'],
        'Sobrance': ['sobrance', 'собранце'],
        'Trebišov': ['trebisov', 'требишов'],
        'Sečovce': ['secovce', 'сечовце'],
        'Strážske': ['strazske', 'стражске'],
        'Vranov nad Topľou': ['vranov nad toplou', 'вранов-над-топлоу'],
        'Svidník': ['svidnik', 'свидник'],
        'Giraltovce': ['giraltovce', 'гиралтовце'],
        'Hanušovce nad Topľou': ['hanusovce nad toplou', 'ганушовце-над-топлоу'],
        'Medzilaborce': ['medzilaborce', 'медзилаборце'],
        'Snina': ['snina', 'снина'],
        'Stropkov': ['stropkov', 'стропков'],
        'Sabinov': ['sabinov', 'сабинов'],
        'Lipany': ['lipany', 'липаны'],
        'Kežmarok': ['kezmarok', 'кежмарок'],
        'Levoča': ['levoca', 'левоча'],
        'Stará Ľubovňa': ['stara lubovna', 'стара-любовня'],
        'Svit': ['svit', 'свит'],
        'Vysoké Tatry': ['vysoke tatry', 'высоке-татры'],
        'Gelnica': ['gelnica', 'гелница'],
        'Rožňava': ['rosnava', 'рожнява'],
        'Revúca': ['revuca', 'ревуца'],
        'Rimavská Sobota': ['rimavska sobota', 'римавска-собота']
    },
    'us': {
        'New York': ['new york', 'нью-йорк', 'nyc'],
        'Los Angeles': ['los angeles', 'лос-анджелес', 'la'],
        'Chicago': ['chicago', 'чикаго'],
        'Houston': ['houston', 'хьюстон'],
        'Phoenix': ['phoenix', 'финикс'],
        'Philadelphia': ['philadelphia', 'филадельфия'],
        'San Antonio': ['san antonio', 'сан-антонио'],
        'San Diego': ['san diego', 'сан-диего'],
        'Dallas': ['dallas', 'даллас'],
        'San Jose': ['san jose', 'сан-хосе'],
        'Austin': ['austin', 'остин'],
        'Jacksonville': ['jacksonville', 'джексонвилл'],
        'Fort Worth': ['fort worth', 'форт-уорт'],
        'Columbus': ['columbus', 'колумбус'],
        'Charlotte': ['charlotte', 'шарлотт'],
        'San Francisco': ['san francisco', 'сан-франциско'],
        'Indianapolis': ['indianapolis', 'индианаполис'],
        'Seattle': ['seattle', 'сиэтл'],
        'Denver': ['denver', 'денвер'],
        'Washington': ['washington', 'вашингтон', 'dc'],
        'Boston': ['boston', 'бостон'],
        'El Paso': ['el paso', 'эль-пасо'],
        'Nashville': ['nashville', 'нашвилл'],
        'Detroit': ['detroit', 'детройт'],
        'Oklahoma City': ['oklahoma city', 'оклахома-сити'],
        'Portland': ['portland', 'портленд'],
        'Las Vegas': ['las vegas', 'лас-вегас'],
        'Memphis': ['memphis', 'мемфис'],
        'Louisville': ['louisville', 'луисвилл'],
        'Baltimore': ['baltimore', 'балтимор'],
        'Milwaukee': ['milwaukee', 'милуоки'],
        'Albuquerque': ['albuquerque', 'альбукерке'],
        'Tucson': ['tucson', 'тусон'],
        'Fresno': ['fresno', 'фресно'],
        'Sacramento': ['sacramento', 'сакраменто'],
        'Mesa': ['mesa', 'меса'],
        'Kansas City': ['kansas city', 'канзас-сити'],
        'Atlanta': ['atlanta', 'атланта'],
        'Long Beach': ['long beach', 'лонг-бич'],
        'Colorado Springs': ['colorado springs', 'колорадо-спрингс'],
        'Raleigh': ['raleigh', 'роли'],
        'Miami': ['miami', 'майами'],
        'Virginia Beach': ['virginia beach', 'вирджиния-бич'],
        'Omaha': ['omaha', 'омаха'],
        'Oakland': ['oakland', 'окленд'],
        'Minneapolis': ['minneapolis', 'миннеаполис'],
        'Tulsa': ['tulsa', 'талса'],
        'Arlington': ['arlington', 'арлингтон'],
        'Tampa': ['tampa', 'тампа'],
        'New Orleans': ['new orleans', 'новый-орлеан'],
        'Wichita': ['wichita', 'уичита'],
        'Cleveland': ['cleveland', 'кливленд'],
        'Bakersfield': ['bakersfield', 'бейкерсфилд'],
        'Aurora': ['aurora', 'аврора'],
        'Anaheim': ['anaheim', 'анахайм'],
        'Honolulu': ['honolulu', 'гонолулу'],
        'Santa Ana': ['santa ana', 'санта-ана'],
        'Riverside': ['riverside', 'риверсайд'],
        'Corpus Christi': ['corpus christi', 'корпус-кристи'],
        'Lexington': ['lexington', 'лексингтон'],
        'Stockton': ['stockton', 'стоктон'],
        'Henderson': ['henderson', 'хендерсон'],
        'Saint Paul': ['saint paul', 'сент-пол'],
        'St. Louis': ['st louis', 'сент-луис'],
        'Cincinnati': ['cincinnati', 'цинциннати'],
        'Pittsburgh': ['pittsburgh', 'питтсбург'],
        'Greensboro': ['greensboro', 'гринсборо'],
        'Anchorage': ['anchorage', 'анкоридж'],
        'Plano': ['plano', 'плано'],
        'Lincoln': ['lincoln', 'линкольн'],
        'Orlando': ['orlando', 'орландо'],
        'Irvine': ['irvine', 'ирвайн'],
        'Newark': ['newark', 'ньюарк'],
        'Durham': ['durham', 'дарем'],
        'Chula Vista': ['chula vista', 'чула-виста'],
        'Toledo': ['toledo', 'толедо'],
        'Fort Wayne': ['fort wayne', 'форт-уэйн'],
        'St. Petersburg': ['st petersburg', 'сент-питерсберг'],
        'Laredo': ['laredo', 'ларедо'],
        'Jersey City': ['jersey city', 'джерси-сити'],
        'Chandler': ['chandler', 'чандлер'],
        'Madison': ['madison', 'мэдисон'],
        'Lubbock': ['lubbock', 'лаббок'],
        'Norfolk': ['norfolk', 'норфолк'],
        'Baton Rouge': ['baton rouge', 'батон-руж'],
        'Buffalo': ['buffalo', 'буффало'],
        'San Bernardino': ['san bernardino', 'сан-бернардино'],
        'Modesto': ['modesto', 'модесто'],
        'Fremont': ['fremont', 'фримонт'],
        'Scottsdale': ['scottsdale', 'скоттсдейл'],
        'Glendale': ['glendale', 'глендейл'],
        'Spring Valley': ['spring valley', 'спринг-валли'],
        'Garland': ['garland', 'гарланд'],
        'Hialeah': ['hialeah', 'хайалиа'],
        'Rochester': ['rochester', 'рочестер'],
        'Chesapeake': ['chesapeake', 'чесапик'],
        'Gilbert': ['gilbert', 'гилберт'],
        'Boise': ['boise', 'бойсе'],
        'San Bernardino': ['san bernardino', 'сан-бернардино'],
        'Reno': ['reno', 'рено'],
        'Spokane': ['spokane', 'спокан'],
        'Richmond': ['richmond', 'ричмонд'],
        'Santa Clarita': ['santa clarita', 'санта-кларита'],
        'Mobile': ['mobile', 'мобил'],
        'Des Moines': ['des moines', 'де-мойн'],
        'Tacoma': ['tacoma', 'такома'],
        'Grand Rapids': ['grand rapids', 'гранд-рапидс'],
        'Huntington Beach': ['huntington beach', 'хантингтон-бич'],
        'Akron': ['akron', 'акрон'],
        'Little Rock': ['little rock', 'литл-рок'],
        'Augusta': ['augusta', 'огаста'],
        'Amarillo': ['amarillo', 'амарилло'],
        'Glendale': ['glendale', 'глендейл'],
        'Montgomery': ['montgomery', 'монтгомери'],
        'Birmingham': ['birmingham', 'бирмингем'],
        'Pearl City': ['pearl city', 'перл-сити'],
        'Grand Prairie': ['grand prairie', 'гранд-прери'],
        'Sioux Falls': ['sioux falls', 'су-фолс'],
        'Peoria': ['peoria', 'пеория'],
        'Overland Park': ['overland park', 'оверленд-парк'],
        'Knoxville': ['knoxville', 'ноксвилл'],
        'Worcester': ['worcester', 'вустер'],
        'Brownsville': ['brownsville', 'браунсвилл'],
        'Oxnard': ['oxnard', 'окснард'],
        'Dayton': ['dayton', 'дейтон'],
        'Fort Lauderdale': ['fort lauderdale', 'форт-лодердейл'],
        'Salt Lake City': ['salt lake city', 'солт-лейк-сити'],
        'Huntsville': ['huntsville', 'хантсвилл'],
        'Tallahassee': ['tallahassee', 'таллахасси'],
        'Grand Prairie': ['grand prairie', 'гранд-прери'],
        'Overland Park': ['overland park', 'оверленд-парк'],
        'Tempe': ['tempe', 'темпе'],
        'McKinney': ['mckinney', 'мак-кинни'],
        'Mobile': ['mobile', 'мобил'],
        'Cape Coral': ['cape coral', 'кейп-корал'],
        'Shreveport': ['shreveport', 'шривпорт'],
        'Frisco': ['frisco', 'фриско'],
        'Killeen': ['killeen', 'киллин'],
        'Topeka': ['topeka', 'топика'],
        'Concord': ['concord', 'конкорд'],
        'Thousand Oaks': ['thousand oaks', 'таузанд-окс'],
        'Cedar Rapids': ['cedar rapids', 'сидар-рапидс'],
        'Olathe': ['olathe', 'олати'],
        'Elizabeth': ['elizabeth', 'элизабет'],
        'Waco': ['waco', 'уэйко'],
        'Hartford': ['hartford', 'хартфорд'],
        'Visalia': ['visalia', 'висалия'],
        'Gainesville': ['gainesville', 'гейнсвилл'],
        'Simi Valley': ['simi valley', 'сими-валли'],
        'Stamford': ['stamford', 'стэмфорд'],
        'Bellevue': ['bellevue', 'беллвью'],
        'Miramar': ['miramar', 'мирамар'],
        'Coral Springs': ['coral springs', 'корал-спрингс'],
        'Sterling Heights': ['sterling heights', 'стерлинг-хайтс'],
        'New Haven': ['new haven', 'нью-хейвен'],
        'Carrollton': ['carrollton', 'кэрролтон'],
        'West Valley City': ['west valley city', 'уэст-валли-сити'],
        'West Jordan': ['west jordan', 'уэст-джордан'],
        'Westminster': ['westminster', 'вестминстер'],
        'Santa Clara': ['santa clara', 'санта-клара'],
        'Macon': ['macon', 'мейкон'],
        'Allentown': ['allentown', 'аллентаун'],
        'Abilene': ['abilene', 'абилин'],
        'Beaumont': ['beaumont', 'бомонт'],
        'Odessa': ['odessa', 'одесса'],
        'Wilmington': ['wilmington', 'уилмингтон'],
        'Columbia': ['columbia', 'колумбия'],
        'Fargo': ['fargo', 'фарго'],
        'Evansville': ['evansville', 'эвансвилл'],
        'Richardson': ['richardson', 'ричардсон'],
        'Bend': ['bend', 'бенд'],
        'Norman': ['norman', 'норман'],
        'Broken Arrow': ['broken arrow', 'брокен-арроу'],
        'Murfreesboro': ['murfreesboro', 'мурфрисборо'],
        'Pompano Beach': ['pompano beach', 'помпано-бич'],
        'Lowell': ['lowell', 'лоуэлл'],
        'Surprise': ['surprise', 'сюрпрайз'],
        'Denton': ['denton', 'дентон']
    },
    'ca': {
        'Toronto': ['toronto', 'торонто'],
        'Montreal': ['montreal', 'монреаль'],
        'Vancouver': ['vancouver', 'ванкувер'],
        'Calgary': ['calgary', 'калгари'],
        'Ottawa': ['ottawa', 'оттава'],
        'Edmonton': ['edmonton', 'эдмонтон'],
        'Mississauga': ['mississauga', 'миссиссога'],
        'Winnipeg': ['winnipeg', 'виннипег'],
        'Quebec City': ['quebec city', 'квебек'],
        'Hamilton': ['hamilton', 'гамильтон'],
        'Brampton': ['brampton', 'брэмптон'],
        'Surrey': ['surrey', 'сарри'],
        'Laval': ['laval', 'лаваль'],
        'Halifax': ['halifax', 'галифакс'],
        'London': ['london', 'лондон'],
        'Markham': ['markham', 'маркам'],
        'Vaughan': ['vaughan', 'вон'],
        'Gatineau': ['gatineau', 'гатино'],
        'Saskatoon': ['saskatoon', 'саскатун'],
        'Longueuil': ['longueuil', 'лонгёй'],
        'Burnaby': ['burnaby', 'бернаби'],
        'Regina': ['regina', 'реджайна'],
        'Richmond': ['richmond', 'ричмонд'],
        'Richmond Hill': ['richmond hill', 'ричмонд-хилл'],
        'Oakville': ['oakville', 'оквилл'],
        'Burlington': ['burlington', 'берлингтон'],
        'Greater Sudbury': ['greater sudbury', 'грейтер-садбери'],
        'Sherbrooke': ['sherbrooke', 'шерброк'],
        'Oshawa': ['oshawa', 'ошауа'],
        'Saguenay': ['saguenay', 'сагеней'],
        'Lévis': ['levis', 'леви'],
        'Barrie': ['barrie', 'барри'],
        'Abbotsford': ['abbotsford', 'абботсфорд'],
        'St. Catharines': ['st catharines', 'сент-катаринс'],
        'Trois-Rivières': ['trois-rivieres', 'труа-ривьер'],
        'Cambridge': ['cambridge', 'кембридж'],
        'Whitby': ['whitby', 'уитби'],
        'Coquitlam': ['coquitlam', 'кокитлам'],
        'Guelph': ['guelph', 'гвельф'],
        'Kingston': ['kingston', 'кингстон'],
        'Kelowna': ['kelowna', 'келоуна'],
        'Saanich': ['saanich', 'санич'],
        'Ajax': ['ajax', 'аякс'],
        'Thunder Bay': ['thunder bay', 'тандер-бей'],
        'Terrebonne': ['terrebonne', 'террбон'],
        'St. John\'s': ['st johns', 'сент-джонс'],
        'Waterloo': ['waterloo', 'ватерлоо'],
        'Delta': ['delta', 'дельта'],
        'Chatham-Kent': ['chatham-kent', 'чатам-кент'],
        'Langley': ['langley', 'лэнгли'],
        'North Vancouver': ['north vancouver', 'норт-ванкувер'],
        'Brantford': ['brantford', 'брантфорд'],
        'Nanaimo': ['nanaimo', 'нанаймо'],
        'Red Deer': ['red deer', 'ред-дир'],
        'Kamloops': ['kamloops', 'камлупс'],
        'Lethbridge': ['lethbridge', 'летбридж'],
        'Milton': ['milton', 'милтон'],
        'Moncton': ['moncton', 'монктон'],
        'White Rock': ['white rock', 'уайт-рок'],
        'Airdrie': ['airdrie', 'эрдри'],
        'Pickering': ['pickering', 'пикеринг'],
        'Sault Ste. Marie': ['sault ste marie', 'су-сент-мари'],
        'Sarnia': ['sarnia', 'сарния'],
        'Wood Buffalo': ['wood buffalo', 'вуд-баффало'],
        'New Westminster': ['new westminster', 'нью-вестминстер'],
        'Châteauguay': ['chateauguay', 'шатоге'],
        'Saint-Jean-sur-Richelieu': ['saint-jean-sur-richelieu', 'сен-жан-сюр-ришелье'],
        'Repentigny': ['repentigny', 'репантиньи'],
        'Drummondville': ['drummondville', 'драммондвилль'],
        'Fort McMurray': ['fort mcmurray', 'форт-мак-мюррей'],
        'Prince George': ['prince george', 'принс-джордж'],
        'Salaberry-de-Valleyfield': ['salaberry-de-valleyfield', 'салаберри-де-валлифилд'],
        'Saint-Jérôme': ['saint-jerome', 'сен-жером'],
        'Medicine Hat': ['medicine hat', 'медисин-хат'],
        'Granby': ['granby', 'гранби'],
        'Sherwood Park': ['sherwood park', 'шервуд-парк'],
        'Grande Prairie': ['grande prairie', 'гранд-прери'],
        'St. Albert': ['st albert', 'сент-альберт'],
        'Blainville': ['blainville', 'бленвилль'],
        'Timmins': ['timmins', 'тимминс'],
        'Saint-Hyacinthe': ['saint-hyacinthe', 'сен-иасент'],
        'Aurora': ['aurora', 'аврора'],
        'Welland': ['welland', 'велланд'],
        'North Bay': ['north bay', 'норт-бей'],
        'Beloeil': ['beloeil', 'белей'],
        'Belleville': ['belleville', 'беллвилл'],
        'Mirabel': ['mirabel', 'мирабель'],
        'Shawinigan': ['shawinigan', 'шавиниган'],
        'Dollard-des-Ormeaux': ['dollard-des-ormeaux', 'доллар-дез-ормо'],
        'Brandon': ['brandon', 'брандон'],
        'Rimouski': ['rimouski', 'римуски'],
        'Chilliwack': ['chilliwack', 'чилливак'],
        'Cornwall': ['cornwall', 'корнуолл'],
        'Victoriaville': ['victoriaville', 'викториавиль'],
        'Vernon': ['vernon', 'вернон'],
        'Duncan': ['duncan', 'данкан'],
        'Saint-Eustache': ['saint-eustache', 'сен-эсташ'],
        'Quinte West': ['quinte west', 'квинт-уэст'],
        'Charlottetown': ['charlottetown', 'шарлоттаун'],
        'Penticton': ['penticton', 'пентиктон'],
        'Sarnia': ['sarnia', 'сарния'],
        'Fredericton': ['fredericton', 'фредериктон'],
        '​​​Joliette': ['joliette', 'жольетт'],
        'Sorel-Tracy': ['sorel-tracy', 'сорель-трейси'],
        'Magog': ['magog', 'магог'],
        'Rouyn-Noranda': ['rouyn-noranda', 'руин-норанда'],
        'Thompson': ['thompson', 'томпсон'],
        'Swift Current': ['swift current', 'свифт-каррент'],
        'Owen Sound': ['owen sound', 'оуэн-саунд'],
        'Joliette': ['joliette', 'жольетт'],
        'Sept-Îles': ['sept-iles', 'сет-иль'],
        'Val-d\'Or': ['val-d-or', 'валь-дор'],
        'Alma': ['alma', 'альма'],
        'Bathurst': ['bathurst', 'батерст'],
        'Thompson': ['thompson', 'томпсон'],
        'Campbellton': ['campbellton', 'кэмпбелтон'],
        'Prince Albert': ['prince albert', 'принс-альберт'],
        'Lloydminster': ['lloydminster', 'лойдминстер'],
        'Yorkton': ['yorkton', 'йорктон'],
        'Estevan': ['estevan', 'эстеван'],
        'Corner Brook': ['corner brook', 'корнер-брук'],
        'Yellowknife': ['yellowknife', 'йеллоунайф'],
        'Hay River': ['hay river', 'хей-ривер'],
        'Whitehorse': ['whitehorse', 'уайтхорс'],
        'Iqaluit': ['iqaluit', 'икалуит']
    },
    'au': {
        'Sydney': ['sydney', 'сидней'],
        'Melbourne': ['melbourne', 'мельбурн'],
        'Brisbane': ['brisbane', 'брисбен'],
        'Perth': ['perth', 'перт'],
        'Adelaide': ['adelaide', 'аделаида'],
        'Gold Coast': ['gold coast', 'голд-кост'],
        'Newcastle': ['newcastle', 'ньюкасл'],
        'Canberra': ['canberra', 'канберра'],
        'Sunshine Coast': ['sunshine coast', 'саншайн-кост'],
        'Wollongong': ['wollongong', 'вуллонгонг'],
        'Hobart': ['hobart', 'хобарт'],
        'Geelong': ['geelong', 'джилонг'],
        'Townsville': ['townsville', 'таунсвилл'],
        'Cairns': ['cairns', 'кэрнс'],
        'Darwin': ['darwin', 'дарвин'],
        'Toowoomba': ['toowoomba', 'тувумба'],
        'Ballarat': ['ballarat', 'баллараб'],
        'Bendigo': ['bendigo', 'бендиго'],
        'Albury': ['albury', 'олбери'],
        'Launceston': ['launceston', 'лонсестон'],
        'Mackay': ['mackay', 'маккей'],
        'Rockhampton': ['rockhampton', 'рокхэмптон'],
        'Bunbury': ['bunbury', 'банбери'],
        'Bundaberg': ['bundaberg', 'бундаберг'],
        'Coffs Harbour': ['coffs harbour', 'кофс-харбор'],
        'Wagga Wagga': ['wagga wagga', 'вагга-вагга'],
        'Hervey Bay': ['hervey bay', 'херви-бей'],
        'Mildura': ['mildura', 'милдура'],
        'Shepparton': ['shepparton', 'шеппартон'],
        'Port Macquarie': ['port macquarie', 'порт-маккуори'],
        'Gladstone': ['gladstone', 'гладстон'],
        'Tamworth': ['tamworth', 'тэмуорт'],
        'Traralgon': ['traralgon', 'тралгон'],
        'Orange': ['orange', 'орандж'],
        'Bowral': ['bowral', 'боурал'],
        'Geraldton': ['geraldton', 'джералдтон'],
        'Kalgoorlie': ['kalgoorlie', 'калгурли'],
        'Warrnambool': ['warrnambool', 'уорнамбул'],
        'Bathurst': ['bathurst', 'батерст'],
        'Dubbo': ['dubbo', 'дабо'],
        'Palmerston': ['palmerston', 'палмерстон'],
        'Nowra': ['nowra', 'наура'],
        'Warragul': ['warragul', 'уаррагул'],
        'Alice Springs': ['alice springs', 'алис-спрингс'],
        'Devonport': ['devonport', 'девонпорт'],
        'Mount Gambier': ['mount gambier', 'маунт-гамбир'],
        'Griffith': ['griffith', 'гриффит'],
        'Lismore': ['lismore', 'лисмор'],
        'Albany': ['albany', 'олбани'],
        'Horsham': ['horsham', 'хоршам'],
        'Broken Hill': ['broken hill', 'брокен-хилл'],
        'Moe': ['moe', 'мо'],
        'Sale': ['sale', 'сейл'],
        'Armidale': ['armidale', 'армидейл'],
        'Goulburn': ['goulburn', 'гулбурн'],
        'Whyalla': ['whyalla', 'уайалла'],
        'Murray Bridge': ['murray bridge', 'мюррей-бридж'],
        'Burnie': ['burnie', 'берни'],
        'Port Augusta': ['port augusta', 'порт-огаста'],
        'Kadina': ['kadina', 'кадина'],
        'Port Pirie': ['port pirie', 'порт-пири'],
        'Mount Barker': ['mount barker', 'маунт-баркер'],
        'Gawler': ['gawler', 'гоулер'],
        'Esperance': ['esperance', 'эсперанс'],
        'Mandurah': ['mandurah', 'мандура'],
        'Broome': ['broome', 'брум'],
        'Busselton': ['busselton', 'басселтон'],
        'Port Hedland': ['port hedland', 'порт-хедланд'],
        'Katherine': ['katherine', 'кэтрин'],
        'Tennant Creek': ['tennant creek', 'теннант-крик'],
        'Nhulunbuy': ['nhulunbuy', 'нхулунбай']
    },
    'it': {
        'Rome': ['rome', 'roma', 'рим'],
        'Milan': ['milan', 'milano', 'милан'],
        'Naples': ['naples', 'napoli', 'неаполь'],
        'Turin': ['turin', 'torino', 'турин'],
        'Palermo': ['palermo', 'палермо'],
        'Genoa': ['genoa', 'genova', 'генуя'],
        'Bologna': ['bologna', 'болонья'],
        'Florence': ['florence', 'firenze', 'флоренция'],
        'Bari': ['bari', 'бари'],
        'Catania': ['catania', 'катания'],
        'Venice': ['venice', 'venezia', 'венеция'],
        'Verona': ['verona', 'верона'],
        'Messina': ['messina', 'мессина'],
        'Padua': ['padua', 'padova', 'падуя'],
        'Trieste': ['trieste', 'триест'],
        'Taranto': ['taranto', 'таранто'],
        'Brescia': ['brescia', 'брешия'],
        'Prato': ['prato', 'прато'],
        'Reggio Calabria': ['reggio calabria', 'реджо-калабрия'],
        'Modena': ['modena', 'модена'],
        'Reggio Emilia': ['reggio emilia', 'реджо-эмилия'],
        'Perugia': ['perugia', 'перуджа'],
        'Ravenna': ['ravenna', 'равенна'],
        'Livorno': ['livorno', 'ливорно'],
        'Cagliari': ['cagliari', 'кальяри'],
        'Foggia': ['foggia', 'фоджа'],
        'Rimini': ['rimini', 'римини'],
        'Salerno': ['salerno', 'салерно'],
        'Ferrara': ['ferrara', 'феррара'],
        'Sassari': ['sassari', 'сассари'],
        'Latina': ['latina', 'латина'],
        'Giugliano in Campania': ['giugliano', 'джульяно'],
        'Monza': ['monza', 'монца'],
        'Syracuse': ['syracuse', 'siracusa', 'сиракузы'],
        'Pescara': ['pescara', 'пескара'],
        'Bergamo': ['bergamo', 'бергамо'],
        'Forlì': ['forli', 'форли'],
        'Trento': ['trento', 'тренто'],
        'Vicenza': ['vicenza', 'виченца'],
        'Terni': ['terni', 'терни'],
        'Bolzano': ['bolzano', 'больцано'],
        'Novara': ['novara', 'новара'],
        'Piacenza': ['piacenza', 'пьяченца'],
        'Ancona': ['ancona', 'анкона'],
        'Andria': ['andria', 'андрия'],
        'Arezzo': ['arezzo', 'арреццо'],
        'Udine': ['udine', 'удине'],
        'Cesena': ['cesena', 'чезена'],
        'Lecce': ['lecce', 'лечче'],
        'Pesaro': ['pesaro', 'пезаро'],
        'Barletta': ['barletta', 'барлетта'],
        'Alessandria': ['alessandria', 'алессандрия'],
        'La Spezia': ['la spezia', 'ла-специя'],
        'Pisa': ['pisa', 'пиза'],
        'Catanzaro': ['catanzaro', 'катанцаро'],
        'Pistoia': ['pistoia', 'пистойя'],
        'Como': ['como', 'комо'],
        'Cremona': ['cremona', 'кремона'],
        'Cosenza': ['cosenza', 'козенца'],
        'Lamezia Terme': ['lamezia terme', 'ламеция-терме'],
        'Massa': ['massa', 'масса'],
        'Lucca': ['lucca', 'лукка'],
        'Fiumicino': ['fiumicino', 'фьюмичино'],
        'Palma di Montechiaro': ['palma di montechiaro', 'пальма-ди-монтекьяро'],
        'Guidonia Montecelio': ['guidonia montecelio', 'гвидония-монтечелио'],
        'Trani': ['trani', 'трани'],
        'Carpi': ['carpi', 'карпи'],
        'Imola': ['imola', 'имола'],
        'Brindisi': ['brindisi', 'бриндизи'],
        'Velletri': ['velletri', 'веллетри'],
        'Viterbo': ['viterbo', 'витербо'],
        'Ragusa': ['ragusa', 'рагуза'],
        'Pozzuoli': ['pozzuoli', 'поццуоли'],
        'Casoria': ['casoria', 'казория'],
        'Matera': ['matera', 'матера'],
        'Caltanissetta': ['caltanissetta', 'кальтаниссетта'],
        'Castellammare di Stabia': ['castellammare di stabia', 'кастелламмаре-ди-стабия'],
        'Portici': ['portici', 'портичи'],
        'Ercolano': ['ercolano', 'эрколано'],
        'Caserta': ['caserta', 'казерта'],
        'Bitonto': ['bitonto', 'битонто'],
        'Cava de\' Tirreni': ['cava de tirreni', 'кава-де-тиррени'],
        'San Severo': ['san severo', 'сан-северо'],
        'Altamura': ['altamura', 'альтамура'],
        'Cerignola': ['cerignola', 'чериньола'],
        'Molfetta': ['molfetta', 'мольфетта'],
        'Asti': ['asti', 'асти'],
        'Gallarate': ['gallarate', 'галларате'],
        'Varese': ['varese', 'варезе'],
        'Faenza': ['faenza', 'фаэнца'],
        'Sesto San Giovanni': ['sesto san giovanni', 'сесто-сан-джованни'],
        'Cinisello Balsamo': ['cinisello balsamo', 'чинизелло-бальсамо'],
        'Legnano': ['legnano', 'леньяно'],
        'Busto Arsizio': ['busto arsizio', 'бусто-арсицио'],
        'Rho': ['rho', 'ро'],
        'Cologno Monzese': ['cologno monzese', 'колоньо-монцезе'],
        'Desio': ['desio', 'дезио'],
        'Seregno': ['seregno', 'сереньо'],
        'Carate Brianza': ['carate brianza', 'карате-брианца'],
        'Lissone': ['lissone', 'лиссоне'],
        'Cesano Maderno': ['cesano maderno', 'чезано-мадерно'],
        'Limbiate': ['limbiate', 'лимбиате'],
        'Nova Milanese': ['nova milanese', 'нова-миланезе'],
        'Muggiò': ['muggio', 'муджо'],
        'Paderno Dugnano': ['paderno dugnano', 'падерно-дуньяно']
    },
    'es': {
        'Madrid': ['madrid', 'мадрид'],
        'Barcelona': ['barcelona', 'барселона'],
        'Valencia': ['valencia', 'валенсия'],
        'Seville': ['seville', 'sevilla', 'севилья'],
        'Zaragoza': ['zaragoza', 'сарагоса'],
        'Málaga': ['malaga', 'малага'],
        'Murcia': ['murcia', 'мурсия'],
        'Palma': ['palma', 'пальма'],
        'Las Palmas de Gran Canaria': ['las palmas', 'лас-пальмас'],
        'Bilbao': ['bilbao', 'бильбао'],
        'Alicante': ['alicante', 'аликанте'],
        'Córdoba': ['cordoba', 'кордоба'],
        'Valladolid': ['valladolid', 'вальядолид'],
        'Vigo': ['vigo', 'виго'],
        'Gijón': ['gijon', 'хихон'],
        'L\'Hospitalet de Llobregat': ['hospitalet', 'оспиталет'],
        'Granada': ['granada', 'гранада'],
        'Vitoria-Gasteiz': ['vitoria', 'витория'],
        'A Coruña': ['a coruna', 'ла-корунья'],
        'Elche': ['elche', 'эльче'],
        'Oviedo': ['oviedo', 'овьедо'],
        'Sabadell': ['sabadell', 'сабадель'],
        'Santa Cruz de Tenerife': ['santa cruz de tenerife', 'санта-крус-де-тенерифе'],
        'Móstoles': ['mostoles', 'мостолес'],
        'Alcalá de Henares': ['alcala de henares', 'алкала-де-энарес'],
        'Pamplona': ['pamplona', 'памплона'],
        'Almería': ['almeria', 'альмерия'],
        'Fuenlabrada': ['fuenlabrada', 'фуэнлабрада'],
        'Leganés': ['leganes', 'леганес'],
        'Donostia': ['donostia', 'san sebastian', 'сан-себастьян'],
        'Burgos': ['burgos', 'бургос'],
        'Albacete': ['albacete', 'альбасете'],
        'Santander': ['santander', 'сантандер'],
        'Getafe': ['getafe', 'хетафе'],
        'Castellón de la Plana': ['castellon', 'кастельон'],
        'Alcorcón': ['alcorcon', 'алкоркон'],
        'Logroño': ['logrono', 'логроньо'],
        'Badajoz': ['badajoz', 'бадахос'],
        'Huelva': ['huelva', 'уэльва'],
        'Salamanca': ['salamanca', 'саламанка'],
        'Lleida': ['lleida', 'лерида'],
        'Tarragona': ['tarragona', 'таррагона'],
        'León': ['leon', 'леон'],
        'Cádiz': ['cadiz', 'кадис'],
        'Dos Hermanas': ['dos hermanas', 'дос-эрманас'],
        'Jaén': ['jaen', 'хаэн'],
        'Ourense': ['ourense', 'оренсе'],
        'Torrejón de Ardoz': ['torrejon de ardoz', 'торрехон-де-ардос'],
        'Parla': ['parla', 'парла'],
        'Mataró': ['mataro', 'матаро'],
        'Algeciras': ['algeciras', 'альхесирас'],
        'Santa Coloma de Gramenet': ['santa coloma', 'санта-колома'],
        'Roquetas de Mar': ['roquetas de mar', 'рокетас-дель-мар'],
        'El Puerto de Santa María': ['el puerto de santa maria', 'эль-пуэрто-де-санта-мария'],
        'Ciudad Real': ['ciudad real', 'сьюдад-реаль'],
        'Cornellà de Llobregat': ['cornella', 'корнелья'],
        'Avilés': ['aviles', 'авилес'],
        'Palencia': ['palencia', 'паленсия'],
        'Gava': ['gava', 'гава'],
        'Barakaldo': ['barakaldo', 'баракальдо'],
        'Viladecans': ['viladecans', 'виладеканс'],
        'Sanlúcar de Barrameda': ['sanlucar de barrameda', 'санлукар-де-баррамеда'],
        'Mijas': ['mijas', 'михас'],
        'Las Rozas de Madrid': ['las rozas', 'лас-росас'],
        'Torrevieja': ['torrevieja', 'торревьеха'],
        'Reus': ['reus', 'реус'],
        'Pozuelo de Alarcón': ['pozuelo de alarcon', 'посуэло-де-аларкон'],
        'Toledo': ['toledo', 'толедо'],
        'Guadalajara': ['guadalajara', 'гвадалахара'],
        'Zamora': ['zamora', 'самора'],
        'Girona': ['girona', 'жирона'],
        'Marbella': ['marbella', 'марбелья'],
        'Cáceres': ['caceres', 'касерес'],
        'Ferrol': ['ferrol', 'ферроль'],
        'Lugo': ['lugo', 'луго'],
        'Santiago de Compostela': ['santiago de compostela', 'сантьяго-де-компостела'],
        'Pontevedra': ['pontevedra', 'понтеведра'],
        'Cuenca': ['cuenca', 'куэнка'],
        'Segovia': ['segovia', 'сеговия'],
        'Ávila': ['avila', 'авила'],
        'Soria': ['soria', 'сория'],
        'Teruel': ['teruel', 'теруэль'],
        'Huesca': ['huesca', 'уэска'],
        'Melilla': ['melilla', 'мелилья'],
        'Ceuta': ['ceuta', 'сеута']
    }
};

function initializeApp() {
    console.log('🚀 GlobalJobHunter v3.2 загружен');
    
    // Инициализация формы поиска
    const searchForm = document.getElementById('job-search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', handleJobSearch);
    }
    
    // Плавная прокрутка
    setupSmoothScroll();
    
    // Автосохранение
    loadSavedPreferences();
    setupAutoSave();
    
    // Анимации при скролле
    setupScrollAnimations();
    
    // Инициализируем умное автозаполнение городов
    initializeSmartCityAutocomplete();
}

function initializeSmartCityAutocomplete() {
    const cityInput = document.querySelector('input[name="city"]');
    if (!cityInput) return;
    
    // Создаем красивый контейнер для подсказок
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'city-autocomplete-dropdown';
    suggestionsContainer.innerHTML = '';
    
    const inputWrapper = cityInput.parentNode;
    inputWrapper.style.position = 'relative';
    inputWrapper.appendChild(suggestionsContainer);
    
    let searchTimeout;
    let selectedIndex = -1;
    
    cityInput.addEventListener('input', handleCityInput);
    cityInput.addEventListener('focus', handleCityInput);
    
    function handleCityInput() {
        const query = cityInput.value.toLowerCase().trim();
        
        clearTimeout(searchTimeout);
        suggestionsContainer.innerHTML = '';
        selectedIndex = -1;
        
        if (query.length < 2) {
            suggestionsContainer.style.display = 'none';
            return;
        }
        
        searchTimeout = setTimeout(() => {
            const suggestions = findCitySuggestions(query);
            displaySuggestions(suggestions);
        }, 200);
    }
    
    function findCitySuggestions(query) {
        const selectedCountries = Array.from(document.querySelectorAll('input[name="countries"]:checked'))
            .map(cb => cb.value);
        
        if (selectedCountries.length === 0) return [];
        
        const suggestions = [];
        
        selectedCountries.forEach(countryCode => {
            const cities = CITIES_DATABASE[countryCode];
            if (!cities) return;
            
            Object.entries(cities).forEach(([cityName, aliases]) => {
                // Проверяем точное совпадение в начале названия города
                if (cityName.toLowerCase().startsWith(query)) {
                    suggestions.push({
                        name: cityName,
                        country: countryCode,
                        priority: 1
                    });
                    return;
                }
                
                // Проверяем содержание в названии города
                if (cityName.toLowerCase().includes(query)) {
                    suggestions.push({
                        name: cityName,
                        country: countryCode,
                        priority: 2
                    });
                    return;
                }
                
                // Проверяем алиасы (альтернативные названия)
                const matchedAlias = aliases.find(alias => alias.includes(query));
                if (matchedAlias) {
                    suggestions.push({
                        name: cityName,
                        country: countryCode,
                        priority: 3,
                        matchedAlias: matchedAlias
                    });
                }
            });
        });
        
        // Сортируем по приоритету и убираем дубликаты
        return suggestions
            .sort((a, b) => a.priority - b.priority)
            .slice(0, 8);
    }
    
    function displaySuggestions(suggestions) {
        if (suggestions.length === 0) {
            suggestionsContainer.style.display = 'none';
            return;
        }
        
        const countryNames = {
            'de': 'Германия', 'pl': 'Польша', 'gb': 'Великобритания',
            'nl': 'Нидерланды', 'fr': 'Франция', 'at': 'Австрия',
            'ch': 'Швейцария', 'be': 'Бельгия', 'dk': 'Дания',
            'se': 'Швеция', 'no': 'Норвегия', 'cz': 'Чехия',
            'sk': 'Словакия', 'us': 'США', 'ca': 'Канада',
            'au': 'Австралия', 'it': 'Италия', 'es': 'Испания'
        };
        
        suggestionsContainer.innerHTML = suggestions.map((suggestion, index) => `
            <div class="city-suggestion-item ${index === selectedIndex ? 'selected' : ''}" data-city="${suggestion.name}" data-index="${index}">
                <div class="city-name">${suggestion.name}</div>
                <div class="city-country">${countryNames[suggestion.country] || suggestion.country}</div>
                ${suggestion.matchedAlias ? `<div class="city-alias">найдено по: ${suggestion.matchedAlias}</div>` : ''}
            </div>
        `).join('');
        
        suggestionsContainer.style.display = 'block';
        
        // Добавляем обработчики кликов
        suggestionsContainer.querySelectorAll('.city-suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                const cityName = item.dataset.city;
                selectCity(cityName);
            });
        });
    }
    
    function selectCity(cityName) {
        cityInput.value = cityName;
        suggestionsContainer.style.display = 'none';
        selectedIndex = -1;
        showAlert(`📍 Выбран город: ${cityName}`, 'success');
        
        // Триггерим событие change для автосохранения
        cityInput.dispatchEvent(new Event('change'));
    }
    
    // Закрытие при клике вне области
    document.addEventListener('click', (e) => {
        if (!inputWrapper.contains(e.target)) {
            suggestionsContainer.style.display = 'none';
            selectedIndex = -1;
        }
    });
    
    // Обновляем при смене стран
    document.querySelectorAll('input[name="countries"]').forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            if (cityInput.value) {
                handleCityInput(); // Перезапускаем поиск с новыми странами
            }
        });
    });
    
    // Навигация клавиатурой
    cityInput.addEventListener('keydown', (e) => {
        const items = suggestionsContainer.querySelectorAll('.city-suggestion-item');
        
        if (items.length === 0) return;
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            updateSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateSelection(items);
        } else if (e.key === 'Enter' && selectedIndex >= 0) {
            e.preventDefault();
            const selectedCity = items[selectedIndex].dataset.city;
            selectCity(selectedCity);
        } else if (e.key === 'Escape') {
            suggestionsContainer.style.display = 'none';
            selectedIndex = -1;
        }
    });
    
    function updateSelection(items) {
        items.forEach((item, index) => {
            item.classList.toggle('selected', index === selectedIndex);
        });
    }
}

function setupAnimations() {
    // Анимация появления элементов
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Наблюдаем за элементами
    document.querySelectorAll('.form-section, .job-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(el);
    });
}

function setupProgressBar() {
    // Создаем прогресс-бар
    const progressContainer = document.createElement('div');
    progressContainer.className = 'progress-container';
    progressContainer.id = 'progress-container';
    
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar-custom';
    progressBar.id = 'progress-bar';
    
    progressContainer.appendChild(progressBar);
    document.body.insertBefore(progressContainer, document.body.firstChild);
}

function showProgress() {
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    
    container.style.display = 'block';
    currentProgress = 0;
    
    // Симуляция прогресса
    progressInterval = setInterval(() => {
        currentProgress += Math.random() * 15;
        if (currentProgress > 90) currentProgress = 90;
        
        bar.style.width = currentProgress + '%';
    }, 500);
}

function hideProgress() {
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    
    // Завершаем до 100%
    clearInterval(progressInterval);
    bar.style.width = '100%';
    
    setTimeout(() => {
        container.style.display = 'none';
        bar.style.width = '0%';
    }, 500);
}

async function handleJobSearch(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Собираем данные
    const searchData = {
        is_refugee: formData.get('is_refugee'),
        selected_jobs: formData.getAll('selected_jobs'),
        countries: formData.getAll('countries'),
        city: formData.get('city')
    };
    
    // Валидация
    if (!searchData.is_refugee) {
        showAlert('❌ Пожалуйста, укажите ваш статус (беженец или нет)', 'warning');
        return;
    }

    if (searchData.selected_jobs.length === 0) {
        showAlert('❌ Выберите хотя бы одну профессию!', 'warning');
        return;
    }
    
    if (searchData.countries.length === 0) {
        showAlert('❌ Выберите хотя бы одну страну!', 'warning');
        return;
    }
    
    // Блокируем кнопку СРАЗУ
    const submitBtn = form.querySelector('button[type="submit"]');
    setButtonLoading(submitBtn, true);
    
    try {
        console.log('🔍 Отправляем запрос на поиск...');
        
        const response = await fetch('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(searchData)
        });
        
        const result = await response.json();
        
        // ИСПРАВЛЕНИЕ: Проверяем статус ответа ПЕРЕД показом модального окна
        if (!response.ok) {
            // Если лимит превышен или другая ошибка - НЕ показываем модальное окно
            throw new Error(result.error || `HTTP ${response.status}`);
        }
        
        if (result.success) {
            // ТОЛЬКО ЗДЕСЬ показываем модальное окно и прогресс
            showLoadingModal();
            showProgress();
            
            // Сохраняем выбор
            savePreferences(searchData);
            
            // Показываем успех
            showSuccessMessage(result.jobs_count, result.search_time);
            
            // Ждем немного для анимации
            setTimeout(() => {
                // Плавный переход на результаты
                window.location.href = result.redirect_url;
            }, 2000);
            
        } else {
            throw new Error(result.error || 'Ошибка поиска');
        }
        
    } catch (error) {
        console.error('❌ Ошибка поиска:', error);
        showAlert(`❌ ${error.message}`, 'danger');
        setButtonLoading(submitBtn, false);
        
        // НЕ вызываем hideLoadingModal() и hideProgress() здесь,
        // так как они могут не быть запущены
    }
}

function showLoadingModal() {
    // Создаем модальное окно если его нет
    let modal = document.getElementById('loading-modal');
    if (!modal) {
        modal = createLoadingModal();
        document.body.appendChild(modal);
    }
    
    const bootstrapModal = new bootstrap.Modal(modal, {
        backdrop: 'static',
        keyboard: false
    });
    bootstrapModal.show();
}

function hideLoadingModal() {
    const modal = document.getElementById('loading-modal');
    if (modal) {
        const bootstrapModal = bootstrap.Modal.getInstance(modal);
        if (bootstrapModal) {
            bootstrapModal.hide();
        }
    }
}

function createLoadingModal() {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'loading-modal';
    modal.setAttribute('tabindex', '-1');
    modal.setAttribute('aria-hidden', 'true');
    
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-body text-center py-5">
                    <div class="loading-spinner mx-auto mb-3"></div>
                    <h5 class="mb-3">🔍 Ищем вакансии...</h5>
                    <p class="text-muted mb-0">Анализируем рынок труда в выбранных странах</p>
                    <div class="progress mt-3" style="height: 6px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                             style="width: 100%"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return modal;
}

function showSuccessMessage(jobsCount, searchTime) {
    // Обновляем модальное окно на успех
    const modalBody = document.querySelector('#loading-modal .modal-body');
    if (modalBody) {
        modalBody.innerHTML = `
            <div class="text-center py-4">
                <div class="mb-3">
                    <i class="bi bi-check-circle-fill text-success" style="font-size: 4rem;"></i>
                </div>
                <h4 class="text-success mb-3">🎉 Поиск завершен!</h4>
                <div class="row">
                    <div class="col-6">
                        <div class="stat-item">
                            <span class="stat-number text-primary">${jobsCount}</span>
                            <span class="stat-label">вакансий найдено</span>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="stat-item">
                            <span class="stat-number text-success">${searchTime}с</span>
                            <span class="stat-label">время поиска</span>
                        </div>
                    </div>
                </div>
                <p class="text-muted mt-3">Переходим к результатам...</p>
                <div class="progress" style="height: 4px;">
                    <div class="progress-bar bg-success" style="width: 100%"></div>
                </div>
            </div>
        `;
    }
}

function setButtonLoading(button, isLoading) {
    if (!button) return;
    
    if (isLoading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2"></span>
            Поиск...
        `;
        button.classList.add('loading');
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText || button.innerHTML;
        button.classList.remove('loading');
    }
}

function showAlert(message, type = 'info') {
    // Удаляем существующие алерты
    document.querySelectorAll('.alert-custom-toast').forEach(alert => alert.remove());
    
    // Создаем новый алерт
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show alert-custom-toast position-fixed`;
    alertDiv.style.cssText = 'top: 80px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Автоскрытие через 5 секунд
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

function setupScrollAnimations() {
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const parallax = document.querySelector('.hero-section');
        if (parallax) {
        }
    });
}

// Сохранение и загрузка предпочтений
function savePreferences(data) {
    try {
        localStorage.setItem('jobhunter_preferences', JSON.stringify(data));
    } catch (error) {
        console.warn('Не удалось сохранить предпочтения:', error);
    }
}

function loadSavedPreferences() {
    try {
        const saved = localStorage.getItem('jobhunter_preferences');
        if (saved) {
            const preferences = JSON.parse(saved);
            
            if (preferences.is_refugee !== undefined) {
                const refugeeRadio = document.querySelector(`input[name="is_refugee"][value="${preferences.is_refugee}"]`);
                if (refugeeRadio) refugeeRadio.checked = true;
            }
            
            if (preferences.selected_jobs) {
                preferences.selected_jobs.forEach(job => {
                    const checkbox = document.querySelector(`input[name="selected_jobs"][value="${job}"]`);
                    if (checkbox) checkbox.checked = true;
                });
            }
            
            if (preferences.countries) {
                document.querySelectorAll('input[name="countries"]').forEach(c => c.checked = false);
                preferences.countries.forEach(country => {
                    const checkbox = document.querySelector(`input[name="countries"][value="${country}"]`);
                    if (checkbox) checkbox.checked = true;
                });
            }
            
            if (preferences.city) {
                const cityInput = document.querySelector('input[name="city"]');
                if (cityInput) cityInput.value = preferences.city;
            }
        }
    } catch (error) {
        console.warn('Не удалось загрузить предпочтения:', error);
    }
}

function setupAutoSave() {
    const form = document.getElementById('job-search-form');
    if (!form) return;
    
    form.addEventListener('change', function() {
        const formData = new FormData(form);
        const data = {
            is_refugee: formData.get('is_refugee'),
            selected_jobs: formData.getAll('selected_jobs'),
            countries: formData.getAll('countries'),
            city: formData.get('city')
        };
        savePreferences(data);
    });
}

// ИСПРАВЛЕНО: Полностью переписана логика быстрого выбора
function selectJobCategory(category, buttonElement) {
    const allCheckboxes = document.querySelectorAll('.job-checkbox');
    const quickSelectButtons = document.querySelectorAll('.quick-select-btn');

    const categoryMapping = {
        'transport': '🚗 ТРАНСПОРТ И ДОСТАВКА',
        'restaurant': '🍽️ ОБЩЕПИТ И СЕРВИС',
        'construction': '🏗️ СТРОИТЕЛЬСТВО И ПРОИЗВОДСТВО',
        'care': '👥 УХОД И МЕДИЦИНА',
        'it': '💻 IT И ТЕХНОЛОГИИ',
        'office': '👔 ОФИС И УПРАВЛЕНИЕ',
        'refugee': '🇺🇦 ДЛЯ УКРАИНСКИХ БЕЖЕНЦЕВ',
        'autoservice': '🔧 АВТОСЕРВИС И ТЕХОБСЛУЖИВАНИЕ',
        'fuel': '⛽ АЗС И ТОПЛИВО',
        'oilgas': '🛢️ НЕФТЬ И ГАЗ',

    };
    
    const targetCategory = categoryMapping[category];
    const categoryBlock = document.querySelector(`div[data-category="${targetCategory}"]`);
    const categoryCheckboxes = categoryBlock ? categoryBlock.querySelectorAll('.job-checkbox') : [];

    // Проверяем, активна ли уже эта кнопка
    const isAlreadyActive = buttonElement.classList.contains('active');

    // Снимаем активность со всех кнопок
    quickSelectButtons.forEach(btn => btn.classList.remove('active'));
    // Снимаем все галочки
    allCheckboxes.forEach(checkbox => checkbox.checked = false);

    if (isAlreadyActive) {
        // Если кнопка была активна, мы просто деактивируем ее и оставляем все галочки снятыми.
        showAlert(`Выбор категории "${targetCategory.substring(2)}" отменен`, 'info');
    } else {
        // Если кнопка не была активна, делаем ее активной и выбираем соответствующие чекбоксы.
        buttonElement.classList.add('active');
        categoryCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        showAlert(`✅ Выбраны профессии из категории: ${targetCategory.substring(2)}`, 'success');
    }
    
    // Триггерим событие change для формы, чтобы автосохранение сработало
    document.getElementById('job-search-form').dispatchEvent(new Event('change'));
}

// Инициализация после полной загрузки
window.addEventListener('load', function() {
    // Скрываем прелоадер если есть
    const preloader = document.getElementById('preloader');
    if (preloader) {
        preloader.style.opacity = '0';
        setTimeout(() => preloader.remove(), 500);
    }
    
    // Добавляем анимацию появления
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease';
        document.body.style.opacity = '1';
    }, 100);
});
// ДОБАВИТЬ ЭТУ ФУНКЦИЮ
// ИСПРАВЛЕННАЯ функция subscribeToEmails в app.js
function subscribeToEmails() {
    console.log('🚀 subscribeToEmails() вызвана'); // Добавляем лог
    
    const emailInput = document.getElementById('subscribe-email');
    const email = emailInput.value.trim();
    
    console.log('📧 Email из поля:', email); // Лог email
    
    if (!email || !email.includes('@')) {
        console.log('❌ Некорректный email'); // Лог ошибки
        showAlert('❌ Введите корректный email адрес', 'warning');
        return;
    }
    
    console.log('🔄 Отправляем запрос на /subscribe'); // Лог запроса
    
    fetch('/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
    })
    .then(response => {
        console.log('📡 Ответ получен, status:', response.status); // Лог ответа
        
        if (response.status === 409) {
            return response.json().then(data => {
                console.log('⚠️ Конфликт подписки:', data);
                showSubscriptionChoiceModal(email, data);
                throw new Error('HANDLED_409');
            });
        } else if (response.ok) {
            return response.json();
        } else {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка подписки');
            });
        }
    })
    .then(data => {
        console.log('✅ Успешная подписка:', data);
        showAlert('✅ ' + data.message, 'success');
        emailInput.value = '';
    })
    .catch(error => {
        if (error.message === 'HANDLED_409') {
            return;
        }
        console.error('❌ Ошибка подписки:', error);
        showAlert('❌ ' + error.message, 'danger');
    });
}

function showSubscriptionChoiceModal(email, data) {
    // ИСПРАВЛЕНИЕ: Проверяем что данные корректны
    if (!data || !data.current_subscription || !data.new_subscription) {
        showAlert('❌ Ошибка данных подписки', 'danger');
        return;
    }
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'subscription-choice-modal';
    
    const currentJobs = data.current_subscription.jobs.slice(0, 3).join(', ') + 
                       (data.current_subscription.jobs.length > 3 ? ` (+${data.current_subscription.jobs.length - 3})` : '');
    const newJobs = data.new_subscription.jobs.slice(0, 3).join(', ') + 
                   (data.new_subscription.jobs.length > 3 ? ` (+${data.new_subscription.jobs.length - 3})` : '');
    
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content" style="border: none; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.2);">
                <div class="modal-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 20px 20px 0 0; padding: 25px;">
                    <div class="d-flex align-items-center">
                        <div class="me-3" style="background: rgba(255,255,255,0.2); border-radius: 50%; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center;">
                            <i class="bi bi-envelope-heart" style="font-size: 1.5rem;"></i>
                        </div>
                        <div>
                            <h4 class="modal-title mb-1" style="font-weight: 600;">Управление подпиской</h4>
                            <small style="opacity: 0.9;">Настройте ваши уведомления</small>
                        </div>
                    </div>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" style="filter: brightness(0) invert(1);"></button>
                </div>
                
                <div class="modal-body" style="padding: 30px;">
                    <div class="alert alert-info" style="border: none; background: linear-gradient(45deg, #e3f2fd, #f3e5f5); border-radius: 15px; border-left: 4px solid #2196F3;">
                        <i class="bi bi-info-circle me-2"></i>
                        <strong>У вас уже есть подписка на этот email!</strong>
                        <br><small class="text-muted">Выберите, как поступить с новыми параметрами поиска</small>
                    </div>
                    
                    <div class="row g-4 mt-2">
                        <div class="col-md-6">
                            <div class="subscription-card current" style="background: linear-gradient(135deg, #f8f9ff 0%, #e8f4fd 100%); border: 2px solid #e3f2fd; border-radius: 15px; padding: 20px; height: 100%; position: relative;">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="subscription-icon" style="background: #2196F3; color: white; border-radius: 10px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
                                        <i class="bi bi-bookmark-check"></i>
                                    </div>
                                    <div>
                                        <h6 class="mb-0" style="color: #2196F3; font-weight: 600;">Текущая подписка</h6>
                                        <small class="text-muted">Действующие настройки</small>
                                    </div>
                                </div>
                                <div class="subscription-details">
                                    <div class="detail-item mb-2">
                                        <i class="bi bi-briefcase text-primary me-2"></i>
                                        <small><strong>Профессии:</strong></small>
                                        <div class="ms-4"><small class="text-muted">${currentJobs}</small></div>
                                    </div>
                                    <div class="detail-item mb-2">
                                        <i class="bi bi-globe text-primary me-2"></i>
                                        <small><strong>Страны:</strong></small>
                                        <div class="ms-4"><small class="text-muted">${data.current_subscription.countries.join(', ')}</small></div>
                                    </div>
                                    <div class="detail-item">
                                        <i class="bi bi-geo-alt text-primary me-2"></i>
                                        <small><strong>Город:</strong></small>
                                        <div class="ms-4"><small class="text-muted">${data.current_subscription.city || 'Не указан'}</small></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <div class="subscription-card new" style="background: linear-gradient(135deg, #f0fff4 0%, #e8f5e8 100%); border: 2px solid #e8f5e8; border-radius: 15px; padding: 20px; height: 100%; position: relative;">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="subscription-icon" style="background: #4CAF50; color: white; border-radius: 10px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
                                        <i class="bi bi-bookmark-plus"></i>
                                    </div>
                                    <div>
                                        <h6 class="mb-0" style="color: #4CAF50; font-weight: 600;">Новая подписка</h6>
                                        <small class="text-muted">Параметры из поиска</small>
                                    </div>
                                </div>
                                <div class="subscription-details">
                                    <div class="detail-item mb-2">
                                        <i class="bi bi-briefcase text-success me-2"></i>
                                        <small><strong>Профессии:</strong></small>
                                        <div class="ms-4"><small class="text-muted">${newJobs}</small></div>
                                    </div>
                                    <div class="detail-item mb-2">
                                        <i class="bi bi-globe text-success me-2"></i>
                                        <small><strong>Страны:</strong></small>
                                        <div class="ms-4"><small class="text-muted">${data.new_subscription.countries.join(', ')}</small></div>
                                    </div>
                                    <div class="detail-item">
                                        <i class="bi bi-geo-alt text-success me-2"></i>
                                        <small><strong>Город:</strong></small>
                                        <div class="ms-4"><small class="text-muted">${data.new_subscription.city || 'Не указан'}</small></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="text-center mt-4">
                        <h6 class="mb-3" style="color: #666;">Выберите действие:</h6>
                    </div>
                </div>
                
                <div class="modal-footer" style="border: none; padding: 20px 30px 30px; gap: 15px;">
                    <button type="button" class="btn btn-outline-secondary flex-fill" data-bs-dismiss="modal" style="border-radius: 12px; padding: 12px; font-weight: 500;">
                        <i class="bi bi-x-circle me-2"></i>Отмена
                    </button>
                    <button type="button" class="btn btn-warning flex-fill" onclick="updateSubscription('${email}', 'replace')" style="border-radius: 12px; padding: 12px; font-weight: 600; box-shadow: 0 4px 15px rgba(255, 193, 7, 0.3);">
                        <i class="bi bi-arrow-repeat me-2"></i>Заменить подписку
                    </button>
                    <button type="button" class="btn btn-success flex-fill" onclick="updateSubscription('${email}', 'merge')" style="border-radius: 12px; padding: 12px; font-weight: 600; box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);">
                        <i class="bi bi-plus-circle me-2"></i>Объединить подписки
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
}

function updateSubscription(email, action) {
    fetch('/subscribe/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, action: action })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('✅ ' + data.message, 'success');
            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('subscription-choice-modal'));
            if (modal) modal.hide();
            // Очищаем поле email
            const emailInput = document.getElementById('subscribe-email');
            if (emailInput) emailInput.value = '';
        } else {
            showAlert('❌ ' + data.error, 'warning');
        }
    })
    .catch(error => {
        console.error('Ошибка обновления подписки:', error);
        showAlert('❌ Ошибка обновления подписки', 'danger');
    });
}

function showManageSubscriptionInfo() {
    alert('📧 Ссылка на управление подпиской будет в каждом email уведомлении!\n\nВы сможете:\n• Изменить профессии\n• Изменить страны\n• Изменить частоту уведомлений\n• Отписаться');
}

function checkSystemStatus() {
    fetch('/health')
        .then(response => {
            if (response.ok) {
                return response.text();
            }
            throw new Error('Сервис недоступен');
        })
        .then(html => {
            // Создаем модальное окно с содержимым статуса
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.id = 'status-modal';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Статус системы</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <iframe srcdoc="${html.replace(/"/g, '&quot;')}" style="width: 100%; height: 400px; border: none;"></iframe>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
            
            // Удаляем модальное окно после закрытия
            modal.addEventListener('hidden.bs.modal', () => {
                modal.remove();
            });
        })
        .catch(error => {
            alert('❌ Ошибка загрузки статуса: ' + error.message);
        });
}

let SEARCH_ID = null;
let PROGRESS_TIMER = null;

function ensureStopButton() {
  const form = document.getElementById('job-search-form');
  if (!form) return;
  const submitBtn = form.querySelector('button[type="submit"]');
  let stopBtn = document.getElementById('stop-search-btn');
  if (!stopBtn) {
    stopBtn = document.createElement('button');
    stopBtn.id = 'stop-search-btn';
    stopBtn.type = 'button';
    stopBtn.className = 'btn-stop-live';
    stopBtn.textContent = 'Остановить поиск и показать найденные вакансии';
    submitBtn.insertAdjacentElement('afterend', stopBtn);
  }
  stopBtn.style.display = 'inline-flex';
  stopBtn.onclick = async () => {
  if (!SEARCH_ID) return;
  stopBtn.disabled = true;
  try {
    const resp = await fetch('/search/stop', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ search_id: SEARCH_ID })
    });
    const data = await resp.json();
    if (data && data.redirect_url) {
      window.location.href = data.redirect_url; // уходим сразу
      return;
    }
    // если редиректа нет — просто ждём прогресса 'done'
  } catch (e) {
    console.error(e);
  } finally {
    stopBtn.disabled = false;
  }
};

}

function renderLiveButton({ jobs_found = 0, current_source = 'Инициализация', completed_sources = [] }) {
  const form = document.getElementById('job-search-form');
  if (!form) return;
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.classList.add('btn-live');
  submitBtn.innerHTML = `
    <div class="live-wrap">
      <div class="live-count">Найдено вакансий: <span id="live-jobs">${jobs_found}</span></div>
      <div class="live-source">Идёт поиск на: <span class="blink">${current_source}</span><span class="dots"></span></div>
      <div class="live-done">${completed_sources.length ? ('Проверено: ' + completed_sources.join(', ')) : '&nbsp;'}</div>
    </div>
  `;
}

async function startLiveSearch(e) {
  e.preventDefault();
  const form = document.getElementById('job-search-form');
  const formData = new FormData(form);
  const payload = {
    is_refugee: formData.get('is_refugee'),
    selected_jobs: formData.getAll('selected_jobs'),
    countries: formData.getAll('countries'),
    city: formData.get('city') || ''
  };
  if (!payload.selected_jobs.length) { alert('Выберите хотя бы одну профессию'); return; }
  if (!payload.countries.length) { alert('Выберите хотя бы одну страну'); return; }

  renderLiveButton({ jobs_found: 0, current_source: 'Старт', completed_sources: [] });
  ensureStopButton();

  const res = await fetch('/search/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    alert(data.error || 'Ошибка запуска поиска');
    return;
  }
  SEARCH_ID = data.search_id;

  const poll = async () => {
    try {
      const r = await fetch(`/search/progress?id=${SEARCH_ID}`);
      const p = await r.json();
      if (p.error) return;

      renderLiveButton({
        jobs_found: p.jobs_found || 0,
        current_source: p.current_source || '—',
        completed_sources: p.completed_sources || []
      });

      if (p.status === 'done') {
        clearInterval(PROGRESS_TIMER);
        window.location.href = p.redirect_url;
      }
    } catch(e) {
      console.error(e);
    }
  };
  await poll();
  PROGRESS_TIMER = setInterval(poll, 600);
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('job-search-form');
  if (form) {
    form.addEventListener('submit', startLiveSearch);
  }
});

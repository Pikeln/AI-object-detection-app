
# backend/rules.py

def hämta_kontroll_mallar():
    return {
        "socket": {
            "titel": "Self-Control: Socket 1-Phase",
            "punkter": ["Mounting checked", "Continuity test performed", "Voltage test L-N"]
        },
        "lighting": {
            "titel": "Self-Control: Lighting",
            "punkter": ["Suspension checked", "Protective earth connected", "Function test performed"]
        },
        "distribution_board": {
            "titel": "Self-Control: Distribution Board",
            "punkter": [
                "Main switch functional",
                "Torque tightening performed",
                "Circuit list posted",
                "RCD tested"
            ]
        },
        "3_pole_switch": {
            "titel": "Self-Control: 3-Pole Switch / MCB",
            "punkter": [
                "Correct rated current",
                "Phase sequence checked",
                "Function testing performed"
            ]
        }
    }

def generera_egenkontroll(objekt_lista):
    """
    Genererar data för egenkontroll baserat på hittade objekt.
    (Placeholder-implementation för att matcha importen i webapp.py)
    """
    return {}

ALIAS = {
    "distribution_board": "distribution_board",
    "mcb_3p": "3_pole_switch",
    "3pol-säk": "3_pole_switch",
    "socket": "socket",
    "light": "lighting",
    "square lighting": "lighting",
    "cross lighting": "lighting",
    "lighting": "lighting",
    "switch": "switch",
    "smoke detector": "smoke detector", # Map english name to itself to be safe if category exists (logic defaults to self but good for clarity)
    "3-pole switch": "3_pole_switch"
}

def hämta_objekt_för_sida(objekt_lista, kategori, antal, sida):
    # Filtrera fram alla objekt som matchar vald kategori
    # Vi kollar om objektets klass (via alias) matchar den valda kategorin
    matchande = []
    for o in objekt_lista:
        obj_klass = o['klass'].lower()
        # Mappa objektets klass till en kategori (defaulta till klassnamnet om ingen alias finns)
        obj_kategori = ALIAS.get(obj_klass, obj_klass)
        
        if obj_kategori == kategori.lower():
            matchande.append(o)
    
    # Beräkna start- och stoppindex för den valda gruppen
    start = sida * antal
    stopp = start + antal
    
    # Returnera urvalet och det totala antalet för att undvika Unpack-fel
    return matchande[start:stopp], len(matchande)

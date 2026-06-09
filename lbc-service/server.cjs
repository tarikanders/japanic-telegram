// server.ts
var import_http = require("http");
var import_url = require("url");

// node_modules/leboncoin-api-search/src/constants.ts
var HEADERS = {
  Host: "api.leboncoin.fr",
  Connection: "keep-alive",
  Accept: "application/json",
  "User-Agent": "LBC;iOS;16.4.1;iPhone;phone;AFACB532-200B-476A-98B3-B2346A97EA54;wifi;6.102.0;24.32.1930",
  api_key: "ba0c2dad52b3ec",
  "Accept-Language": "fr-FR,fr;q=0.9",
  "Content-Type": "application/json",
  Cookie: "didomi_token=eyJ2ZW5kb3JzIjp7ImRpc2FibGVkIjpbImM6YWRqdXN0Z21iLXBjY05kSkJRIiwiYzpicmFuY2gtVjJkRUJSeEoiLCJjOmNhYmxhdG9saS1uUm1WYXdwMiIsImM6Zm9ydHZpc2lvbi1pZTZiWFR3OSIsImM6aW5mZWN0aW91cy1tZWRpYSIsImM6aGFzb2ZmZXItOFl5TVR0WGkiLCJjOnNhbm9tYSIsImM6cHVib2NlYW4tYjZCSk10c2UiLCJjOmFiLXRhc3R5IiwiYzpyZWFsemVpdGctYjZLQ2t4eVYiLCJjOmludG93b3dpbi1xYXp0NXRHaSIsImM6cHVycG9zZWxhLTN3NFpmS0tEIiwiYzptb2JpZnkiLCJjOnRpa3Rvay1LWkFVUUxaOSIsImM6aWxsdW1hdGVjLUNodEVCNGVrIiwiYzp3aGVuZXZlcm0tOFZZaHdiMlAiLCJjOnJldGFyZ2V0ZXItYmVhY29uIiwiYzpqcXVlcnkiLCJjOnJ0YXJnZXQtR2VmTVZ5aUMiLCJjOnlvcm1lZGlhcy1xbkJXaFF5UyIsImM6YWRsaWdodG5pLXRXWkdyZWhUIiwiYzppbnRpbWF0ZS1tZXJnZXIiLCJjOnNuYXBpbmMteWhZbkpaZlQiLCJjOmRpZG9taSIsImM6cXdlcnRpemUtemRuZ0UyaHgiLCJjOnJldmxpZnRlci1jUnBNbnA1eCIsImM6c2NoaWJzdGVkLU1RUFhhcXloIiwiYzpjbG91ZGZsYXJlIiwiYzp2aWFudC00N3gyWWhmNyIsImM6cm9ja2VyYm94LWZUTThFSjlQIiwiYzphZG1vdGlvbiIsImM6bWF4Y2RuLWlVTXROcWNMIiwiYzphZHZhbnNlLUg2cWJheG5RIiwiYzpsa3FkLWNVOVFtQjZXIiwiYzphcHBzZmx5ZXItWXJQZEdGNjMiLCJjOnZ1YmxlLWNNQ0pWeDRlIiwiYzpzd2F2ZW4tTFlCcmltQVoiLCJjOnNmci1NZHBpN2tmTiIsImM6b3NjYXJvY29tLUZSY2hOZG5IIiwiYzp0aGlyZHByZXNlLVNzS3dtSFZLIiwiYzphZGltby1QaFVWbTZGRSIsImM6cmV0ZW5jeS1DTGVyWmlHTCIsImM6Y3JlYXRlanMiLCJjOmdyZWVuaG91c2UtUUtiR0JrczQiLCJjOmxlbW9tZWRpYS16YllocDJRYyIsImM6emFub3giLCJjOmxiY2ZyYW5jZSIsImM6cmVzZWFyY2gtbm93IiwiYzptYXl0cmljc2ctQVMzNVlhbTkiLCJjOmFmZmlsaW5ldCIsImM6cm9ja3lvdSIsImM6cmFkdmVydGlzLVNKcGEyNUg4IiwiYzpha2FtYWkiLCJjOnR1cmJvIiwiYzphdC1pbnRlcm5ldCJdLCJlbmFibGVkIjpbXX0sInB1cnBvc2VzIjp7ImRpc2FibGVkIjpbIm1lYXN1cmVfYWRfcGVyZm9ybWFuY2UiLCJzZWxlY3RfcGVyc29uYWxpemVkX2FkcyIsImNvb2tpZXMiLCJtYXJrZXRfcmVzZWFyY2giLCJnZW9sb2NhdGlvbl9kYXRhIiwiZGV2aWNlX2NoYXJhY3RlcmlzdGljcyIsImltcHJvdmVfcHJvZHVjdHMiLCJwZXJzb25uYWxpc2F0aW9ubWFya2V0aW5nIiwiY3JlYXRlX2Fkc19wcm9maWxlIiwicHJpeCIsImV4cGVyaWVuY2V1dGlsaXNhdGV1ciIsInVzZV9saW1pdGVkX2RhdGFfdG9fc2VsZWN0X2NvbnRlbnQiLCJtZXN1cmVhdWRpZW5jZSIsInNlbGVjdF9iYXNpY19hZHMiXSwiZW5hYmxlZCI6WyJuZWNlc3NhaXJlcyJdfSwidXNlcl9pZCI6IjdDQTRBQ0NBLUU1ODgtNDA1NS05MkFBLUJCNzFFRDA2QjRCQiJ9; datadome=fY_S~5q2DUa_EgbQ_geUQr9aRO~TjqElbKqJcUrq~Mjfc~sp2nY9pX9Qw2GrGu6wDynd6oLCou~bUL69LG6DkOtDUaJB6Gfr_sqQZsN4pt0tG8NPuy_25tkGSn6z_s_M"
};
var REGIONS = [
  {
    rName: "Alsace",
    rId: "1",
    hasNear: true,
    nearRegions: ["1", "10", "15"],
    departments: [
      {
        dId: "67",
        name: "Bas-Rhin",
        hasNear: true,
        deeplink: "bas_rhin",
        nearDepartments: ["67", "57", "68", "88"]
      },
      {
        dId: "68",
        name: "Haut-Rhin",
        hasNear: true,
        deeplink: "haut_rhin",
        nearDepartments: ["68", "67", "88", "90"]
      }
    ],
    deeplink: "alsace"
  },
  {
    rName: "Aquitaine",
    rId: "2",
    hasNear: true,
    nearRegions: ["2", "14", "16", "20"],
    departments: [
      {
        dId: "24",
        name: "Dordogne",
        hasNear: true,
        deeplink: "dordogne",
        nearDepartments: ["24", "16", "17", "19", "33", "46", "47", "87"]
      },
      {
        dId: "33",
        name: "Gironde",
        hasNear: true,
        deeplink: "gironde",
        nearDepartments: ["33", "17", "24", "40", "47"]
      },
      {
        dId: "40",
        name: "Landes",
        hasNear: true,
        deeplink: "landes",
        nearDepartments: ["40", "32", "33", "47", "64"]
      },
      {
        dId: "47",
        name: "Lot-et-Garonne",
        hasNear: true,
        deeplink: "lot_et_garonne",
        nearDepartments: ["47", "24", "32", "33", "40", "46", "82"]
      },
      {
        dId: "64",
        name: "Pyr\xE9n\xE9es-Atlantiques",
        hasNear: true,
        deeplink: "pyrenees_atlantiques",
        nearDepartments: ["64", "32", "40", "65"]
      }
    ],
    deeplink: "aquitaine"
  },
  {
    rName: "Auvergne",
    rId: "3",
    hasNear: true,
    nearRegions: ["3", "5", "7", "13", "14", "16", "22"],
    departments: [
      {
        dId: "3",
        name: "Allier",
        hasNear: true,
        deeplink: "allier",
        nearDepartments: ["3", "18", "23", "42", "58", "63", "71"]
      },
      {
        dId: "15",
        name: "Cantal",
        hasNear: true,
        deeplink: "cantal",
        nearDepartments: ["15", "12", "19", "43", "46", "48", "63"]
      },
      {
        dId: "43",
        name: "Haute-Loire",
        hasNear: true,
        deeplink: "haute_loire",
        nearDepartments: ["43", "7", "15", "42", "48", "63"]
      },
      {
        dId: "63",
        name: "Puy-de-D\xF4me",
        hasNear: true,
        deeplink: "puy_de_dome",
        nearDepartments: ["63", "3", "15", "19", "23", "42", "43"]
      }
    ],
    deeplink: "auvergne"
  },
  {
    rName: "Auvergne-Rh\xF4ne-Alpes",
    rId: "30",
    hasNear: false,
    nearRegions: ["30"],
    deeplink: "auvergne_rhone_alpes"
  },
  {
    rName: "Basse-Normandie",
    rId: "4",
    hasNear: true,
    nearRegions: ["4", "6", "7", "11", "18"],
    departments: [
      {
        dId: "14",
        name: "Calvados",
        hasNear: true,
        deeplink: "calvados",
        nearDepartments: ["14", "27", "50", "61", "76"]
      },
      {
        dId: "50",
        name: "Manche",
        hasNear: true,
        deeplink: "manche",
        nearDepartments: ["50", "14", "35", "53", "61"]
      },
      {
        dId: "61",
        name: "Orne",
        hasNear: true,
        deeplink: "orne",
        nearDepartments: ["61", "14", "27", "28", "50", "53", "72"]
      }
    ],
    deeplink: "basse_normandie"
  },
  {
    rName: "Bourgogne",
    rId: "5",
    hasNear: true,
    nearRegions: ["5", "3", "7", "8", "10", "12", "22"],
    departments: [
      {
        dId: "21",
        name: "C\xF4te-d'Or",
        hasNear: true,
        deeplink: "cote_d_or",
        nearDepartments: ["21", "10", "39", "52", "58", "70", "71", "89"]
      },
      {
        dId: "58",
        name: "Ni\xE8vre",
        hasNear: true,
        deeplink: "nievre",
        nearDepartments: ["58", "3", "18", "21", "45", "71", "89"]
      },
      {
        dId: "71",
        name: "Sa\xF4ne-et-Loire",
        hasNear: true,
        deeplink: "saone_et_loire",
        nearDepartments: ["71", "1", "3", "21", "39", "42", "58", "69"]
      },
      {
        dId: "89",
        name: "Yonne",
        hasNear: true,
        deeplink: "yonne",
        nearDepartments: ["89", "10", "21", "45", "58", "77"]
      }
    ],
    deeplink: "bourgogne"
  },
  {
    rName: "Bourgogne-Franche-Comt\xE9",
    rId: "31",
    hasNear: false,
    nearRegions: ["31"],
    deeplink: "bourgogne_franche_comte"
  },
  {
    rName: "Bretagne",
    rId: "6",
    hasNear: true,
    nearRegions: ["6", "4", "18"],
    departments: [
      {
        dId: "22",
        name: "C\xF4tes-d'Armor",
        hasNear: true,
        deeplink: "cotes_d_armor",
        nearDepartments: ["22", "29", "35", "56"]
      },
      {
        dId: "29",
        name: "Finist\xE8re",
        hasNear: true,
        deeplink: "finistere",
        nearDepartments: ["29", "22", "56"]
      },
      {
        dId: "35",
        name: "Ille-et-Vilaine",
        hasNear: true,
        deeplink: "ille_et_vilaine",
        nearDepartments: ["35", "22", "44", "49", "50", "53", "56"]
      },
      {
        dId: "56",
        name: "Morbihan",
        hasNear: true,
        deeplink: "morbihan",
        nearDepartments: ["56", "22", "29", "35", "44"]
      }
    ],
    deeplink: "bretagne"
  },
  {
    rName: "Centre",
    rId: "7",
    hasNear: true,
    nearRegions: ["7", "3", "4", "5", "11", "12", "14", "18", "20"],
    departments: [
      {
        dId: "18",
        name: "Cher",
        hasNear: true,
        deeplink: "cher",
        nearDepartments: ["18", "3", "36", "41", "45", "58"]
      },
      {
        dId: "28",
        name: "Eure-et-Loir",
        hasNear: true,
        deeplink: "eure_et_loir",
        nearDepartments: ["28", "27", "41", "45", "61", "72", "78", "91"]
      },
      {
        dId: "36",
        name: "Indre",
        hasNear: true,
        deeplink: "indre",
        nearDepartments: ["36", "3", "18", "23", "37", "41", "86", "87"]
      },
      {
        dId: "37",
        name: "Indre-et-Loire",
        hasNear: true,
        deeplink: "indre_et_loire",
        nearDepartments: ["37", "36", "41", "49", "72", "86"]
      },
      {
        dId: "41",
        name: "Loir-et-Cher",
        hasNear: true,
        deeplink: "loir_et_cher",
        nearDepartments: ["41", "18", "28", "36", "37", "45", "72"]
      },
      {
        dId: "45",
        name: "Loiret",
        hasNear: true,
        deeplink: "loiret",
        nearDepartments: ["45", "18", "28", "41", "58", "77", "89", "91"]
      }
    ],
    deeplink: "centre"
  },
  {
    rName: "Centre-Val de Loire",
    rId: "37",
    hasNear: false,
    nearRegions: ["37"],
    deeplink: "centre_val_de_loire"
  },
  {
    rName: "Champagne-Ardenne",
    rId: "8",
    hasNear: true,
    nearRegions: ["8", "5", "10", "12", "15", "19"],
    departments: [
      {
        dId: "8",
        name: "Ardennes",
        hasNear: true,
        deeplink: "ardennes",
        nearDepartments: ["8", "180", "190", "150", "2", "51", "55"]
      },
      {
        dId: "10",
        name: "Aube",
        hasNear: true,
        deeplink: "aube",
        nearDepartments: ["10", "21", "51", "52", "77", "89"]
      },
      {
        dId: "51",
        name: "Marne",
        hasNear: true,
        deeplink: "marne",
        nearDepartments: ["51", "2", "8", "10", "52", "55", "77"]
      },
      {
        dId: "52",
        name: "Haute-Marne",
        hasNear: true,
        deeplink: "haute_marne",
        nearDepartments: ["52", "10", "21", "51", "55", "70", "88"]
      }
    ],
    deeplink: "champagne_ardenne"
  },
  {
    rName: "Corse",
    rId: "9",
    hasNear: false,
    nearRegions: ["9"],
    deeplink: "corse"
  },
  {
    rName: "Franche-Comt\xE9",
    rId: "10",
    hasNear: true,
    nearRegions: ["10", "1", "5", "8", "15", "22"],
    departments: [
      {
        dId: "25",
        name: "Doubs",
        hasNear: true,
        deeplink: "doubs",
        nearDepartments: ["25", "39", "70", "90"]
      },
      {
        dId: "39",
        name: "Jura",
        hasNear: true,
        deeplink: "jura",
        nearDepartments: ["39", "1", "21", "25", "70", "71"]
      },
      {
        dId: "70",
        name: "Haute-Sa\xF4ne",
        hasNear: true,
        deeplink: "haute_saone",
        nearDepartments: ["70", "21", "25", "52", "88", "90"]
      },
      {
        dId: "90",
        name: "Territoire de Belfort",
        hasNear: true,
        deeplink: "territoire_de_belfort",
        nearDepartments: ["90", "25", "68", "70"]
      }
    ],
    deeplink: "franche_comte"
  },
  {
    rName: "Grand Est",
    rId: "33",
    hasNear: false,
    nearRegions: ["33"],
    deeplink: "grand_est"
  },
  {
    rName: "Guadeloupe",
    rId: "23",
    hasNear: false,
    nearRegions: ["23"],
    deeplink: "guadeloupe"
  },
  {
    rName: "Guyane",
    rId: "25",
    hasNear: false,
    nearRegions: ["25"],
    deeplink: "guyane"
  },
  {
    rName: "Haute-Normandie",
    rId: "11",
    hasNear: true,
    nearRegions: ["11", "4", "7", "12", "19"],
    departments: [
      {
        dId: "27",
        name: "Eure",
        hasNear: true,
        deeplink: "eure",
        nearDepartments: ["27", "14", "28", "60", "61", "76", "78", "95"]
      },
      {
        dId: "76",
        name: "Seine-Maritime",
        hasNear: true,
        deeplink: "seine_maritime",
        nearDepartments: ["76", "14", "27", "60", "80"]
      }
    ],
    deeplink: "haute_normandie"
  },
  {
    rName: "Hauts-de-France",
    rId: "32",
    hasNear: false,
    nearRegions: ["32"],
    deeplink: "hauts_de_france"
  },
  {
    rName: "Ile-de-France",
    rId: "12",
    hasNear: true,
    nearRegions: ["12", "5", "7", "8", "11", "19"],
    departments: [
      {
        dId: "75",
        name: "Paris",
        hasNear: true,
        deeplink: "paris",
        nearDepartments: ["75", "92", "93", "94"]
      },
      {
        dId: "77",
        name: "Seine-et-Marne",
        hasNear: true,
        deeplink: "seine_et_marne",
        nearDepartments: ["77", "2", "10", "45", "51", "60", "89", "91", "93", "94", "95"]
      },
      {
        dId: "78",
        name: "Yvelines",
        hasNear: true,
        deeplink: "yvelines",
        nearDepartments: ["78", "27", "28", "91", "92", "95"]
      },
      {
        dId: "91",
        name: "Essonne",
        hasNear: true,
        deeplink: "essonne",
        nearDepartments: ["91", "28", "45", "77", "78", "92", "94"]
      },
      {
        dId: "92",
        name: "Hauts-de-Seine",
        hasNear: true,
        deeplink: "hauts_de_seine",
        nearDepartments: ["92", "75", "78", "91", "95", "94"]
      },
      {
        dId: "93",
        name: "Seine-Saint-Denis",
        hasNear: true,
        deeplink: "seine_saint_denis",
        nearDepartments: ["93", "75", "77", "92", "94", "95"]
      },
      {
        dId: "94",
        name: "Val-de-Marne",
        hasNear: true,
        deeplink: "val_de_marne",
        nearDepartments: ["94", "75", "77", "91", "92", "93"]
      },
      {
        dId: "95",
        name: "Val-d'Oise",
        hasNear: true,
        deeplink: "val_d_oise",
        nearDepartments: ["95", "27", "60", "77", "78", "92", "93"]
      }
    ],
    deeplink: "ile_de_france"
  },
  {
    rName: "Languedoc-Roussillon",
    rId: "13",
    hasNear: true,
    nearRegions: ["13", "3", "16", "21", "22"],
    departments: [
      {
        dId: "11",
        name: "Aude",
        hasNear: true,
        deeplink: "aude",
        nearDepartments: ["11", "9", "31", "34", "66", "81"]
      },
      {
        dId: "30",
        name: "Gard",
        hasNear: true,
        deeplink: "gard",
        nearDepartments: ["30", "7", "12", "13", "34", "48", "84"]
      },
      {
        dId: "34",
        name: "H\xE9rault",
        hasNear: true,
        deeplink: "herault",
        nearDepartments: ["34", "11", "12", "30", "81"]
      },
      {
        dId: "48",
        name: "Loz\xE8re",
        hasNear: true,
        deeplink: "lozere",
        nearDepartments: ["48", "7", "12", "15", "30", "43"]
      },
      {
        dId: "66",
        name: "Pyr\xE9n\xE9es-Orientales",
        hasNear: true,
        deeplink: "pyrenees_orientales",
        nearDepartments: ["66", "9", "11"]
      }
    ],
    deeplink: "languedoc_roussillon"
  },
  {
    rName: "Limousin",
    rId: "14",
    hasNear: true,
    nearRegions: ["14", "2", "3", "7", "16", "20"],
    departments: [
      {
        dId: "19",
        name: "Corr\xE8ze",
        hasNear: true,
        deeplink: "correze",
        nearDepartments: ["19", "15", "23", "24", "46", "63", "87"]
      },
      {
        dId: "23",
        name: "Creuse",
        hasNear: true,
        deeplink: "creuse",
        nearDepartments: ["23", "3", "19", "36", "63", "87"]
      },
      {
        dId: "87",
        name: "Haute-Vienne",
        hasNear: true,
        deeplink: "haute_vienne",
        nearDepartments: ["87", "16", "19", "23", "24", "36", "86"]
      }
    ],
    deeplink: "limousin"
  },
  {
    rName: "Lorraine",
    rId: "15",
    hasNear: true,
    nearRegions: ["15", "1", "8", "10"],
    departments: [
      {
        dId: "54",
        name: "Meurthe-et-Moselle",
        hasNear: true,
        deeplink: "meurthe_et_moselle",
        nearDepartments: ["54", "55", "57", "88"]
      },
      {
        dId: "55",
        name: "Meuse",
        hasNear: true,
        deeplink: "meuse",
        nearDepartments: ["55", "180", "8", "51", "52", "54", "88"]
      },
      {
        dId: "57",
        name: "Moselle",
        hasNear: true,
        deeplink: "moselle",
        nearDepartments: ["57", "180", "54", "67"]
      },
      {
        dId: "88",
        name: "Vosges",
        hasNear: true,
        deeplink: "vosges",
        nearDepartments: ["88", "52", "54", "55", "67", "68", "70"]
      }
    ],
    deeplink: "lorraine"
  },
  {
    rName: "Martinique",
    rId: "24",
    hasNear: false,
    nearRegions: ["24"],
    deeplink: "martinique"
  },
  {
    rName: "Midi-Pyr\xE9n\xE9es",
    rId: "16",
    hasNear: true,
    nearRegions: ["16", "2", "3", "13", "14"],
    departments: [
      {
        dId: "9",
        name: "Ari\xE8ge",
        hasNear: true,
        deeplink: "ariege",
        nearDepartments: ["9", "11", "31", "66"]
      },
      {
        dId: "12",
        name: "Aveyron",
        hasNear: true,
        deeplink: "aveyron",
        nearDepartments: ["12", "15", "30", "34", "46", "48", "81", "82"]
      },
      {
        dId: "31",
        name: "Haute-Garonne",
        hasNear: true,
        deeplink: "haute_garonne",
        nearDepartments: ["31", "9", "11", "32", "65", "81", "82"]
      },
      {
        dId: "32",
        name: "Gers",
        hasNear: true,
        deeplink: "gers",
        nearDepartments: ["32", "31", "40", "47", "64", "65", "82"]
      },
      {
        dId: "46",
        name: "Lot",
        hasNear: true,
        deeplink: "lot",
        nearDepartments: ["46", "12", "15", "19", "24", "47", "82"]
      },
      {
        dId: "65",
        name: "Hautes-Pyr\xE9n\xE9es",
        hasNear: true,
        deeplink: "hautes_pyrenees",
        nearDepartments: ["65", "31", "32", "64"]
      },
      {
        dId: "81",
        name: "Tarn",
        hasNear: true,
        deeplink: "tarn",
        nearDepartments: ["81", "11", "12", "31", "34", "82"]
      },
      {
        dId: "82",
        name: "Tarn-et-Garonne",
        hasNear: true,
        deeplink: "tarn_et_garonne",
        nearDepartments: ["82", "12", "31", "32", "46", "47", "81"]
      }
    ],
    deeplink: "midi_pyrenees"
  },
  {
    rName: "Nord-Pas-de-Calais",
    rId: "17",
    hasNear: true,
    nearRegions: ["17", "19"],
    departments: [
      {
        dId: "59",
        name: "Nord",
        hasNear: true,
        deeplink: "nord",
        nearDepartments: ["59", "150", "130", "2", "80", "62"]
      },
      {
        dId: "62",
        name: "Pas-de-Calais",
        hasNear: true,
        deeplink: "pas_de_calais",
        nearDepartments: ["62", "59", "80"]
      }
    ],
    deeplink: "nord_pas_de_calais"
  },
  {
    rName: "Normandie",
    rId: "34",
    hasNear: false,
    nearRegions: ["34"],
    deeplink: "normandie"
  },
  {
    rName: "Nouvelle-Aquitaine",
    rId: "35",
    hasNear: false,
    nearRegions: ["35"],
    deeplink: "nouvelle_aquitaine"
  },
  {
    rName: "Occitanie",
    rId: "36",
    hasNear: false,
    nearRegions: ["36"],
    deeplink: "occitanie"
  },
  {
    rName: "Pays de la Loire",
    rId: "18",
    hasNear: true,
    nearRegions: ["18", "4", "6", "7", "20"],
    departments: [
      {
        dId: "44",
        name: "Loire-Atlantique",
        hasNear: true,
        deeplink: "loire_atlantique",
        nearDepartments: ["44", "35", "49", "56", "85"]
      },
      {
        dId: "49",
        name: "Maine-et-Loire",
        hasNear: true,
        deeplink: "maine_et_loire",
        nearDepartments: ["49", "35", "37", "44", "53", "72", "79", "85", "86"]
      },
      {
        dId: "53",
        name: "Mayenne",
        hasNear: true,
        deeplink: "mayenne",
        nearDepartments: ["53", "35", "49", "50", "61", "72"]
      },
      {
        dId: "72",
        name: "Sarthe",
        hasNear: true,
        deeplink: "sarthe",
        nearDepartments: ["72", "28", "37", "41", "49", "53", "61"]
      },
      {
        dId: "85",
        name: "Vend\xE9e",
        hasNear: true,
        deeplink: "vendee",
        nearDepartments: ["85", "17", "44", "49", "79"]
      }
    ],
    deeplink: "pays_de_la_loire"
  },
  {
    rName: "Picardie",
    rId: "19",
    hasNear: true,
    nearRegions: ["19", "8", "11", "12", "17"],
    departments: [
      {
        dId: "2",
        name: "Aisne",
        hasNear: true,
        deeplink: "aisne",
        nearDepartments: ["2", "150", "8", "51", "59", "60", "77", "80"]
      },
      {
        dId: "60",
        name: "Oise",
        hasNear: true,
        deeplink: "oise",
        nearDepartments: ["60", "2", "27", "76", "77", "80", "95"]
      },
      {
        dId: "80",
        name: "Somme",
        hasNear: true,
        deeplink: "somme",
        nearDepartments: ["80", "2", "60", "62", "76"]
      }
    ],
    deeplink: "picardie"
  },
  {
    rName: "Poitou-Charentes",
    rId: "20",
    hasNear: true,
    nearRegions: ["20", "2", "7", "14", "18"],
    departments: [
      {
        dId: "16",
        name: "Charente",
        hasNear: true,
        deeplink: "charente",
        nearDepartments: ["16", "17", "24", "79", "86", "87"]
      },
      {
        dId: "17",
        name: "Charente-Maritime",
        hasNear: true,
        deeplink: "charente_maritime",
        nearDepartments: ["17", "16", "24", "33", "79", "85"]
      },
      {
        dId: "79",
        name: "Deux-S\xE8vres",
        hasNear: true,
        deeplink: "deux_sevres",
        nearDepartments: ["79", "16", "17", "49", "85", "86"]
      },
      {
        dId: "86",
        name: "Vienne",
        hasNear: true,
        deeplink: "vienne",
        nearDepartments: ["86", "16", "37", "36", "49", "79", "87"]
      }
    ],
    deeplink: "poitou_charentes"
  },
  {
    rName: "Provence-Alpes-C\xF4te d'Azur",
    rId: "21",
    hasNear: true,
    nearRegions: ["21", "13", "22"],
    departments: [
      {
        dId: "4",
        name: "Alpes-de-Haute-Provence",
        hasNear: true,
        deeplink: "alpes_de_haute_provence",
        nearDepartments: ["4", "5", "6", "26", "83", "84"]
      },
      {
        dId: "5",
        name: "Hautes-Alpes",
        hasNear: true,
        deeplink: "hautes_alpes",
        nearDepartments: ["5", "4", "26", "38", "73"]
      },
      {
        dId: "6",
        name: "Alpes-Maritimes",
        hasNear: true,
        deeplink: "alpes_maritimes",
        nearDepartments: ["6", "4", "83"]
      },
      {
        dId: "13",
        name: "Bouches-du-Rh\xF4ne",
        hasNear: true,
        deeplink: "bouches_du_rhone",
        nearDepartments: ["13", "30", "83", "84"]
      },
      {
        dId: "83",
        name: "Var",
        hasNear: true,
        deeplink: "var",
        nearDepartments: ["83", "4", "6", "13", "84"]
      },
      {
        dId: "84",
        name: "Vaucluse",
        hasNear: true,
        deeplink: "vaucluse",
        nearDepartments: ["84", "4", "7", "13", "26", "30", "83"]
      }
    ],
    deeplink: "provence_alpes_cote_d_azur"
  },
  {
    rName: "Rh\xF4ne-Alpes",
    rId: "22",
    hasNear: true,
    nearRegions: ["22", "3", "5", "10", "13", "21"],
    departments: [
      {
        dId: "1",
        name: "Ain",
        hasNear: true,
        deeplink: "ain",
        nearDepartments: ["1", "38", "39", "69", "71", "73", "74"]
      },
      {
        dId: "7",
        name: "Ard\xE8che",
        hasNear: true,
        deeplink: "ardeche",
        nearDepartments: ["7", "26", "30", "38", "42", "43", "48", "84"]
      },
      {
        dId: "26",
        name: "Dr\xF4me",
        hasNear: true,
        deeplink: "drome",
        nearDepartments: ["26", "4", "5", "7", "38", "84"]
      },
      {
        dId: "38",
        name: "Is\xE8re",
        hasNear: true,
        deeplink: "isere",
        nearDepartments: ["38", "1", "5", "7", "26", "42", "69", "73"]
      },
      {
        dId: "42",
        name: "Loire",
        hasNear: true,
        deeplink: "loire",
        nearDepartments: ["42", "3", "7", "26", "38", "43", "63", "69", "71"]
      },
      {
        dId: "69",
        name: "Rh\xF4ne",
        hasNear: true,
        deeplink: "rhone",
        nearDepartments: ["69", "1", "38", "42", "71"]
      },
      {
        dId: "73",
        name: "Savoie",
        hasNear: true,
        deeplink: "savoie",
        nearDepartments: ["73", "1", "5", "38", "74"]
      },
      {
        dId: "74",
        name: "Haute-Savoie",
        hasNear: true,
        deeplink: "haute_savoie",
        nearDepartments: ["74", "1", "73"]
      }
    ],
    deeplink: "rhone_alpes"
  },
  {
    rName: "R\xE9union",
    rId: "26",
    hasNear: false,
    nearRegions: ["26"],
    deeplink: "reunion"
  }
];

// node_modules/leboncoin-api-search/src/utils.ts
function levenshteinDistance(s, t) {
  if (!s.length) return t.length;
  if (!t.length) return s.length;
  const arr = [];
  for (let i = 0; i <= t.length; i++) {
    arr[i] = [i];
    for (let j = 1; j <= s.length; j++) {
      arr[i][j] = i === 0 ? j : Math.min(
        arr[i - 1][j] + 1,
        arr[i][j - 1] + 1,
        arr[i - 1][j - 1] + (s[j - 1] === t[i - 1] ? 0 : 1)
      );
    }
  }
  return arr[t.length][s.length];
}
function simpleText(text) {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

// node_modules/leboncoin-api-search/src/location.ts
function getLocationByCode(code) {
  code = code.toString();
  const foundRegion = REGIONS.find((region) => region.rId === code);
  if (foundRegion) {
    return {
      region_id: code,
      locationType: "region",
      label: foundRegion.rName
    };
  }
  const foundDepartment = REGIONS.flatMap((region) => region.departments).find(
    (department) => department?.dId === code
  );
  if (foundDepartment) {
    return {
      department_id: code,
      locationType: "department",
      label: foundDepartment.name
    };
  }
  return {
    zipcode: code,
    locationType: "city"
  };
}
function getLocationByName(name) {
  const foundDepartment = _getDepartmentByName(name);
  const foundRegion = _getRegionByName(name);
  if (foundDepartment.distance < foundRegion.distance) {
    return foundDepartment.department;
  } else {
    return foundRegion.region;
  }
}
function _getDepartmentByName(name) {
  const foundDepartment = REGIONS.reduce(
    (acc, region) => {
      const found = region.departments?.find((department) => {
        const distance = levenshteinDistance(simpleText(name), simpleText(department.name));
        return distance < acc.distance;
      });
      if (found) {
        acc.distance = levenshteinDistance(simpleText(name), simpleText(found.name));
        acc.department = {
          department_id: found.dId,
          locationType: "department",
          label: found.name
        };
      }
      return acc;
    },
    { distance: Infinity, department: void 0 }
  );
  return foundDepartment;
}
function _getRegionByName(name) {
  const foundRegion = REGIONS.reduce(
    (acc, region) => {
      const distance = levenshteinDistance(simpleText(name), simpleText(region.rName));
      if (distance < acc.distance) {
        acc.distance = distance;
        acc.region = {
          region_id: region.rId,
          locationType: "region",
          label: region.rName
        };
      }
      return acc;
    },
    { distance: Infinity, region: void 0 }
  );
  return foundRegion;
}

// node_modules/leboncoin-api-search/src/search.ts
async function search(search_filters_input) {
  const search2 = await fetch("https://api.leboncoin.fr/finder/search", {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(_makeFilters(search_filters_input))
  });
  const json = await search2.json();
  return json;
}
function _makeFilters(search_filters_input) {
  const search_filters = {
    filters: {
      category: void 0,
      enums: _makeFiltersEnums(search_filters_input),
      keywords: void 0,
      ranges: _makeFiltersRanges(search_filters_input),
      location: {
        locations: [],
        shippable: true
      }
    },
    limit: search_filters_input.limit || 30,
    offset: search_filters_input.offset || void 0,
    pivot: search_filters_input.pivot || void 0,
    owner_type: search_filters_input.owner_type || "all" /* ALL */,
    sort_by: search_filters_input.sort_by || "date" /* TIME */,
    sort_order: search_filters_input.sort_order || "desc" /* DESC */
  };
  if (search_filters_input.keywords !== void 0) {
    search_filters.filters.keywords = {
      text: search_filters_input.keywords,
      type: search_filters_input?.only_title === true ? "subject" : "all"
    };
  }
  if (search_filters_input.category !== void 0) {
    search_filters.filters.category = { id: search_filters_input.category };
  }
  if (search_filters_input.locations !== void 0) {
    search_filters.filters.location.locations = _makeFiltersLocations(search_filters_input);
    search_filters.filters.location.shippable = search_filters_input.shippable ?? false;
  } else {
    search_filters.filters.location.shippable = search_filters_input.shippable ?? true;
  }
  return search_filters;
}
function _makeFiltersEnums(search_filters_input) {
  const enums = search_filters_input.enums || {};
  if (enums.ad_type === void 0) {
    enums.ad_type = ["offer"];
  }
  return enums;
}
function _makeFiltersRanges(search_filters_input) {
  const ranges = search_filters_input.ranges || {};
  if (search_filters_input.price_min !== void 0 || search_filters_input.price_max !== void 0) {
    ranges.price = {};
    ranges.price.min = search_filters_input.price_min ? search_filters_input.price_min : void 0;
    ranges.price.max = search_filters_input.price_max ? search_filters_input.price_max : void 0;
  }
  return ranges;
}
function _makeFiltersLocations(search_filters_input) {
  const locations = [];
  search_filters_input.locations?.forEach((location) => {
    if (typeof location === "string" && location.match(/[a-z]/i)) {
      const locationInfo = getLocationByName(location);
      if (locationInfo) {
        locations.push(locationInfo);
      }
    } else {
      const locationInfo = getLocationByCode(location);
      if (locationInfo) {
        locations.push(locationInfo);
      }
    }
  });
  return locations;
}

// server.ts
var PORT = process.env.LBC_PORT || 3001;
(0, import_http.createServer)(async (req, res) => {
  if (req.method !== "GET") {
    res.writeHead(405);
    res.end();
    return;
  }
  const url = new import_url.URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname !== "/search") {
    res.writeHead(404);
    res.end();
    return;
  }
  const p = url.searchParams;
  const query = p.get("query") || "";
  const brand = p.get("brand");
  const model = p.get("model");
  const yearMin = p.get("year_min");
  const yearMax = p.get("year_max");
  const kmMax = p.get("km_max");
  const priceMin = p.get("price_min");
  const priceMax = p.get("price_max");
  if (!query && !brand) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "query or brand required" }));
    return;
  }
  try {
    const params = {
      category: "2",
      limit: 35
    };
    if (query) params.keywords = query;
    if (brand || model) {
      params.enums = {};
      if (brand) params.enums.brand = [brand];
      if (model) params.enums.model = [model];
    }
    const ranges = {};
    if (yearMin || yearMax) {
      ranges.regdate = {};
      if (yearMin) ranges.regdate.min = parseInt(yearMin);
      if (yearMax) ranges.regdate.max = parseInt(yearMax);
    }
    if (kmMax) {
      ranges.mileage = { max: parseInt(kmMax) };
    }
    if (Object.keys(ranges).length) params.ranges = ranges;
    if (priceMin) params.price_min = parseInt(priceMin);
    if (priceMax) params.price_max = parseInt(priceMax);
    const raw = await search(params);
    const ads = (raw?.ads || []).slice(0, 20).map((ad) => ({
      id: ad.list_id,
      title: ad.subject,
      price: ad.price?.[0] ?? null,
      url: ad.url,
      city: ad.location?.city ?? null,
      mileage: ad.attributes?.find((a) => a.key === "mileage")?.value_label ?? null,
      year: ad.attributes?.find((a) => a.key === "regdate")?.value_label ?? null,
      fuel: ad.attributes?.find((a) => a.key === "fuel")?.value_label ?? null,
      image: ad.images?.thumb_url ?? null,
      date: ad.first_publication_date ?? null
    }));
    const prices = ads.map((a) => a.price).filter((p2) => p2 !== null && p2 > 0);
    const avg = prices.length ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length) : null;
    const min = prices.length ? Math.min(...prices) : null;
    const max = prices.length ? Math.max(...prices) : null;
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ads, stats: { avg, min, max, count: ads.length, total: raw?.total ?? 0 } }));
  } catch (e) {
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: e.message }));
  }
}).listen(PORT, () => console.log(`LBC service listening on port ${PORT}`));

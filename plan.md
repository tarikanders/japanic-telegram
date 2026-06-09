Plan — Fiabiliser année/km des enchères (Tier 1 + Tier 2 complet)

 Context

 Le tracker d'enchères auto (/workspaces/L3S6/JapanicTelegram/backend/) associe deux types de messages Telegram :
 - Annonces (listings) : "2014 model G63 amg. 29k km. Start price 32000€" → année, modèle, km, prix de départ. Pas de numéro de lot.
 - Résultats (auctions) : message multi-lignes avec en-tête "Today's results (06/04)" puis "65032, 911 turbo 124000€ not sold" → lot, modèle, prix final, statut.

 Aujourd'hui seulement 1 565 / 26 539 enchères (5,9 %) ont une année fiable (match_confidence='high'). Trois causes identifiées par exploration code+data :

 1. Les annonces n'ont pas de model_normalized — on compare le modèle propre des enchères au texte brut bordélique des annonces (carera, cls63 amg shooting brake). ~78 % des
 résultats semblent « sans candidat » : c'est un artefact de chaîne, pas une vraie absence.
 2. L'assignation est gloutonne — chaque enchère prend la meilleure annonce libre dans l'ordre des dates ; une enchère traitée tôt vole l'annonce qui était le bon match unique
 d'une enchère plus tardive.
 3. Signaux déterministes jetés au scrape : la date d'en-tête (06/04), le texte brut, et l'ordre des lignes des résultats (qui reflète probablement l'ordre de publication des
 annonces) ne sont stockés nulle part → impossible à récupérer sans re-scrape.

 Objectif : récupérer le bon modèle avec le bon km et la bonne année de façon fiable. Décision validée : Tier 1 (gain immédiat sur la DB actuelle) puis Tier 2 (re-scrape
 enrichi + matching déterministe).

 Métrique de succès : % enchères en 'high'. Base = 5,9 %. Cible Tier 1 : nette hausse (l'artefact de 78 % disparaît). Cible Tier 2 : convertir une grande part des « review »
 (ambiguïté réelle même-modèle) en « high » via la date d'en-tête + l'alignement positionnel par bande de lot.

 ---
 TIER 1 — Améliorer le matching sur la DB EXISTANTE (sans re-scrape)

 T1.1 — Ajouter listings.model_normalized + backfill

 - backend/models.py (classe Listing) : ajouter model_normalized = Column(String, index=True).
 - Nouveau backend/scripts/migrate_listing_normalized.py — calqué exactement sur migrate_confidence.py (idempotent : PRAGMA table_info, ALTER TABLE, dry-run vs --apply) :
   - _add_column() : si absent → ALTER TABLE listings ADD COLUMN model_normalized VARCHAR.
   - _backfill(apply) : pour chaque Listing, model_normalized = normalize_model(listing.model_raw) (réutilise services/normalizer.py:normalize_model).
   - Après backfill : CREATE INDEX IF NOT EXISTS ix_listings_model_normalized ON listings(model_normalized) (index APRÈS remplissage pour éviter les réécritures).
   - Rapport cardinalité distinct avant/après (même style que _renormalize).

 T1.2 — Le linker compare normalisé ↔ normalisé

 Fichier backend/services/linker.py. On change les entrées, pas les maths de scoring (model_score, _core_match, _core_tokens, score_listing restent — ils opèrent très bien sur
 du normalisé, qui contient toujours les codes M3/G63).
 - Ajouter from services.normalizer import normalize_model.
 - rank_free_listings(...) : normaliser le modèle auction en tête (auction_model = normalize_model(auction_model)), dériver key de là, préfiltrer sur
 Listing.model_normalized.ilike(...), scorer avec lst.model_normalized. → les deux appelants (sync.py, link_auctions) profitent sans churn de signature.
 - link_auctions(...) : bucketiser sur _clean_model(lst.model_normalized) ; clé par-auction sur au.model_normalized ; scorer avec lst.model_normalized.

 T1.3 — Remplacer l'assignation GLOUTONNE par une assignation GLOBALE optimale par lot temporel

 Dans linker.py, nouvelles fonctions :
 - _assign_batch(auctions, listings) -> dict[auction_id -> (listing, score, margin)] :
   - Matrice de coût C[i,j] = -score_listing(...) ; paires interdites (None) → coût sentinelle (1e6).
   - scipy.optimize.linear_sum_assignment(C) (Hungarian, optimal, n petit par bucket).
   - Jeter les paires assignées dont le score réel est None (sentinelle).
   - Marge = score(i,j) − second_meilleur_faisable de la même ligne → préserve la sémantique MATCH_MARGIN_MIN mais relative à l'optimum global.
 - Dépendance scipy : import gardé + fallback sans dépendance _assign_batch_greedy_global (trie tous les triplets faisables (auction, listing, score) par score décroissant,
 assigne en consommation mutuelle ≈ quasi-optimal). scipy devient une optimisation, pas une exigence dure.
 try:
     from scipy.optimize import linear_sum_assignment
     _HAS_SCIPY = True
 except ImportError:
     _HAS_SCIPY = False
 - Ajouter scipy à backend/requirements.txt (avec fallback, donc non bloquant).
 - Réécrire le corps de link_auctions(...) : buckets normalisés → _assign_batch par bucket → même logique d'écriture existante (high → copie year/km/start_price + consommation
 1:1 ; review → efface + hint ; none → efface). Les clés du dict stats restent identiques → fix_db.py inchangé.

 T1.4 — Re-tuner la confiance

 classify_ranked / logique de marge par batch : règle inchangée (high ssi candidat faisable unique OU best − second ≥ MATCH_MARGIN_MIN). Ne PAS toucher MATCH_MARGIN_MIN (6.0)
 à l'aveugle ; ajuster seulement après mesure (T1.6).

 T1.5 — Séquence de migration / re-link

 1. python scripts/migrate_listing_normalized.py (dry-run) → revue → --apply.
 2. python scripts/migrate_confidence.py --apply (existant, idempotent).
 3. python scripts/fix_db.py --dry-run → inspecter nouvelles stats high/review/unmatched.
 4. python scripts/fix_db.py --apply → auto-backup timestampé du .db puis re-link global.
 5. python scripts/audit_db.py → confirmer hausse du high + triplets sur-partagés bas.
 L'ordre compte : normalisation des annonces (1) AVANT le re-link (4).

 T1.6 — Vérification Tier 1

 - Métrique via audit_db.py : % high avant/après (base 1 565/26 539).
 - Tests dans backend/test_pipeline.py :
   - test_linker_global_assignment() : 2 enchères + 2 annonces où le glouton mésassignerait → l'assignation globale donne à chacune la bonne annonce, les 2 en high.
   - test_linker_uses_normalized() : annonce model_raw="bmw M3 coupe" / model_normalized="BMW M3" matche une enchère model_normalized="BMW M3" que l'ancien chemin raw-vs-raw
 ratait.
   - Mettre à jour _isolated_db / test_sync_pipeline : renseigner model_normalized sur les listings insérés (ou appeler normalize_model).
 - Lancer : cd backend && python -m pytest test_pipeline.py tests/ -v.

 ---
 TIER 2 — Capturer les signaux déterministes (scraper + re-scrape complet)

 T2.1 — Nouvelles colonnes

 backend/models.py :
 - Auction : raw_text = Column(Text), result_line_index = Column(Integer) (ordinal du lot dans son message résultat), grouped_id = Column(BigInteger, nullable=True).
 - Listing : raw_text = Column(Text), grouped_id = Column(BigInteger, nullable=True).
 - Nouveau backend/scripts/migrate_raw_signals.py (même motif idempotent) : ajoute ces colonnes aux deux tables si absentes.

 T2.2 — Parser la date d'en-tête + l'ordre des lignes

 backend/services/parser.py :
 - RESULTS_HEADER_PATTERN = re.compile(r"today'?s results\s*\((\d{1,2})/(\d{1,2})\)", re.IGNORECASE).
 - parse_results_header_date(text, fallback_year) -> Optional[date] : MM/DD sans année → inférer depuis l'année du timestamp message, avec garde de bascule d'année (en-tête
 mois ≫ mois message → année précédente). None si pas d'en-tête.
 - ParsedAuctionResult.line_index: Optional[int] ; parse_results_message assigne line_index = position parmi les lignes résultat parsées.

 T2.3 — Date d'en-tête = VRAIE auction_date + stockage des signaux

 backend/services/scraper.py (run_sync) et backend/sync.py :
 - Message résultat : auction_date = parse_results_header_date(text, message.date.year) or msg_date.
 - Stocker raw_text=text, result_line_index=r.line_index, grouped_id=message.grouped_id.
 - Annonce : raw_text=text, grouped_id.
 - Unifier le matching incrémental : remplacer le matching inline ILIKE de scraper.py (qui ne renseigne PAS match_confidence) par un appel à linker.find_best_listing →
 confiance cohérente entre sync incrémental et re-link batch.

 T2.4 — Alignement positionnel par bande de lot (signal fort)

 Dans linker.py, passe optionnelle (activée si données Tier 2 présentes), exécutée AVANT le fallback bipartite global :
 - _lot_band(lot_number) -> str : bande = lot // 1000 (65xxx/70xxx/73xxx = maisons/sessions d'enchère).
 - Au sein d'un groupe (auction_date, band) : résultats ordonnés par result_line_index (≈ ordre du message) ; annonces des ~7 j précédents ordonnées par (posted_date,
 telegram_message_id).
 - _align_session(results, listings) -> list[(auction, listing, score)] : alignement monotone par DP type Needleman-Wunsch (il y a ~1,3–1,8× plus d'annonces que de résultats →
 sous-séquence). Score local = model_score existant + cohérence positionnelle (pénaliser les croisements).
 - Confiance : une paire à la fois fort-modèle ET ordre-cohérente → high, même si la marge modèle seule était mince. Si le signal d'ordre est faible → dégrader vers
 l'assignation globale Tier 1 (pas de faux high silencieux).

 T2.5 — Mécanique du re-scrape

 - Les champs Tier 2 ne se remplissent qu'en avant → re-scrape complet requis (texte brut jamais stocké).
 - auction_date devient la date d'en-tête → change la clé de dédup (lot_number, auction_date). Re-scraper dans une DB NEUVE (pas mélanger anciennes lignes date-timestamp et
 nouvelles date-en-tête).
 - Process : nouvelle DB → SyncCheckpoint.last_message_id=0 → run_sync relit tout le canal (rate-limité FloodWait, déjà géré par le scraper). Lancer hors-pointe.
 - Déploiement : la DB de prod vit sur le volume GCS de Cloud Run. Re-scraper en local dans une DB neuve, valider, puis remplacer le fichier sur le volume (ou re-sync via
 l'endpoint admin avec WebSocket logs sur Admin.jsx).

 T2.6 — Vérification Tier 2

 - Tests test_pipeline.py :
   - test_parse_results_header() : "Today's results (06/04)\n65032, 911 turbo 124000€ not sold" → date 06/04 (année inférée), premier résultat line_index=0.
   - test_positional_alignment() : groupe (date, band) avec 3 « BMW M3 » identiques + annonces ordonnées → l'alignement récupère le bon 1:1 et marque high.
   - Mettre à jour sync/pipeline pour renseigner raw_text, result_line_index, grouped_id.
 - Métrique : même % high ; viser la conversion d'une part des « review » Tier 1 en « high ».

 ---
 Fichiers touchés (récapitulatif)

 Tier 1 :
 - backend/services/linker.py — normalisation des deux côtés ; _assign_batch (scipy + fallback glouton-global) ; confiance par marge.
 - backend/models.py — Listing.model_normalized.
 - backend/scripts/migrate_listing_normalized.py (nouveau).
 - backend/sync.py — modèle normalisé vers find_best_listing.
 - backend/requirements.txt — scipy (fallback gracieux).
 - backend/test_pipeline.py — tests assignation globale + matching normalisé.

 Tier 2 :
 - backend/models.py — raw_text, result_line_index, grouped_id.
 - backend/services/parser.py — RESULTS_HEADER_PATTERN, parse_results_header_date, line_index.
 - backend/services/scraper.py + backend/sync.py — stockage signaux + date d'en-tête + unifier matching via find_best_listing.
 - backend/services/linker.py — _lot_band, _align_session (pré-passe positionnelle).
 - backend/scripts/migrate_raw_signals.py (nouveau).
 - backend/test_pipeline.py — tests en-tête + alignement.

 Séquence d'exécution recommandée

 1. Tier 1 complet (code + migration + re-link + tests) → mesurer le nouveau % high sur la DB actuelle. Gain immédiat, zéro risque.
 2. Tier 2 scraper/parser/models (colonnes, parsing en-tête, stockage) + tests unitaires.
 3. Re-scrape complet dans une DB neuve (hors-pointe, FloodWait géré).
 4. Linker avec pré-passe positionnelle sur les données fraîches → mesurer le % high final.
 5. Déployer la nouvelle DB sur Cloud Run + push du code.

 Risques clés

 - scipy dans requirements (~30 Mo) → mitigé par fallback import-gardé.
 - Plus de candidats normalisés → peut surfacer de la vraie ambiguïté (devient « review », pas « high ») : c'est précisément ce que Tier 2 résout.
 - Re-scrape lent / FloodWait → planifier hors-pointe, DB neuve.
 - Inférence d'année MM/DD aux bornes d'année → garde + test unitaire.
 - Hypothèse positionnelle (ordre résultats ≈ ordre annonces) empirique → la DP doit dégrader proprement vers l'assignation globale quand le signal d'ord
 re est faible.
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
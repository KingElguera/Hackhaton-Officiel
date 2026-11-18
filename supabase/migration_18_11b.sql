-- Marcel — colonnes de suivi du chantier pour l'API du front (18/11, 2e partie). Ré-exécutable.
alter table public.projets add column if not exists fiche jsonb;            -- la fiche saisie (sans les photos)
alter table public.projets add column if not exists analyse_photos jsonb;   -- ce que Hugging Face a lu sur les photos
alter table public.projets add column if not exists questions jsonb;        -- questions générées par le code
alter table public.projets add column if not exists reponses jsonb;
alter table public.projets add column if not exists choix_delegues jsonb;   -- ce que Marcel a décidé, avec la raison
alter table public.projets add column if not exists sessions jsonb;         -- agents H lancés (fournisseur, session_id, live_url)
alter table public.projets add column if not exists dernier_suivi timestamptz; -- dernier appel à H (limite 5 req/min)
alter table public.projets add column if not exists devis jsonb;

-- Marcel — mise à jour du 18/11 (à coller dans Supabase → SQL Editor → Run). Ré-exécutable.

-- 1. Ce qu'attend le workflow n8n d'Erwan « Mail de résultat »
alter table public.projets add column if not exists nom text;
alter table public.projets add column if not exists email_artisan text;
alter table public.projets add column if not exists prenom_artisan text;

create table if not exists public.journal_n8n (
  id          uuid primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  passage_id  text,
  projet_id   uuid references public.projets(id) on delete set null,
  station     text,
  nom_station text,
  statut      text,
  duree_ms    numeric,
  erreur      text
);
alter table public.journal_n8n enable row level security;   -- écrit par n8n (clé service), illisible depuis le front

-- 2. États du chantier alignés sur le front (pret côté front = termine en base, déclencheur du mail)
alter table public.projets drop constraint if exists projets_statut_check;
alter table public.projets add constraint projets_statut_check
  check (statut in ('brouillon','questions','valide','en_recherche','termine','envoye','erreur'));

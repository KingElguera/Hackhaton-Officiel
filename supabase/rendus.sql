-- Marcel — file d'attente des rendus 3D (à coller dans Supabase → SQL Editor → Run, après schema.sql)
-- Ré-exécutable sans risque.
--
-- Le site demande un rendu par l'API (POST /api/rendu) : une ligne « a_faire » est créée ici.
-- L'atelier (atelier.py, sur un poste avec Blender) prend la ligne, génère les meubles en 3D (TRELLIS),
-- lance Blender, dépose les images dans le stockage et passe la ligne à « fait ».

create table if not exists public.rendus (
  id           uuid primary key default gen_random_uuid(),
  created_at   timestamptz not null default now(),
  projet_id    uuid references public.projets(id) on delete set null,
  etat         text not null default 'a_faire'
               check (etat in ('a_faire','en_cours','fait','echec')),
  demande      jsonb not null,                  -- pièce, peinture, sol, ouvertures, meubles (voir docs/MEUBLES_3D.md)
  resultat     jsonb,                           -- images (nom, url, secondes), meubles posés, alertes, durée totale
  erreur       text,
  tentatives   int not null default 0,
  pris_le      timestamptz,
  termine_le   timestamptz
);
create index if not exists rendus_etat_idx on public.rendus(etat, created_at);

alter table public.rendus enable row level security;
do $$ begin
  -- Lecture publique, comme les autres tables. L'écriture passe par la clé de service (API et atelier), jamais par le navigateur.
  create policy "lecture publique" on public.rendus for select using (true);
exception when duplicate_object then null; end $$;

-- Stockage : images rendues (affichées par le site) et objets 3D (cache des meubles).
insert into storage.buckets (id, name, public) values ('rendus', 'rendus', true) on conflict (id) do nothing;
insert into storage.buckets (id, name, public) values ('objets3d', 'objets3d', true) on conflict (id) do nothing;

-- Marcel — schéma Supabase (à coller dans Supabase → SQL Editor → Run)
-- Région : Europe. Ré-exécutable sans risque (create if not exists / on conflict).

-- ------------------------------------------------------------------ fournisseurs
create table if not exists public.fournisseurs (
  id          text primary key,                 -- 'castorama', 'ikea'…
  nom         text not null,
  url         text not null,
  accessible  boolean,                          -- l'agent H peut-il naviguer dessus ?
  obstacle    text,                             -- ex. 'CAPTCHA Cloudflare'
  teste_le    timestamptz,
  notes       text
);

-- ------------------------------------------------------------------ skills (missions réutilisables de l'agent)
create table if not exists public.skills (
  id             uuid primary key default gen_random_uuid(),
  nom            text not null unique,          -- 'releve_prix', 'parcours_marcel'
  description    text,
  agent          text not null default 'h/web-surfer-flash',
  consigne       text not null,                 -- texte envoyé à l'agent ({url}, {produits}, {code_postal} remplacés)
  schema_sortie  jsonb not null,                -- format fixe attendu
  max_steps      int,
  max_time_s     int,
  version        int not null default 1,
  actif          boolean not null default true,
  created_at     timestamptz not null default now()
);

-- ------------------------------------------------------------------ projets (demandes des utilisateurs)
create table if not exists public.projets (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  texte           text,
  photo_url       text,
  code_postal     text,
  budget_eur      numeric,
  niveau          text,
  emplacement     jsonb,                        -- {largeur_mm, profondeur_mm, hauteur_mm, marge_mm}
  besoins         jsonb,
  hors_perimetre  jsonb,
  statut          text not null default 'brouillon'
                  check (statut in ('brouillon','valide','en_recherche','termine','erreur')),
  resultat        jsonb,                        -- achats, planning, guide
  total_eur       numeric,
  fin_travaux     date
);

-- ------------------------------------------------------------------ executions (1 ligne = 1 session d'agent H)
create table if not exists public.executions (
  id                    uuid primary key default gen_random_uuid(),
  created_at            timestamptz not null default now(),
  projet_id             uuid references public.projets(id) on delete set null,
  skill_id              uuid references public.skills(id) on delete set null,
  fournisseur_id        text references public.fournisseurs(id),
  agent                 text not null,           -- 'h/web-surfer-flash' | 'h/web-surfer-pro'
  session_id            text unique,
  live_url              text,
  statut                text not null default 'lancee',  -- lancee, running, completed, idle, failed, timed_out…
  acces_site            text,                    -- ok | partiel | bloque (selon l'agent)
  duree_s               numeric,
  etapes                int,
  cout_credits          numeric,
  erreur                text,
  reponse               jsonb,                   -- réponse brute de l'agent
  nb_produits_attendus  int,
  nb_produits_corrects  int,                     -- calculé par le code (champs obligatoires présents)
  format_respecte       boolean,
  termine_le            timestamptz
);
create index if not exists executions_projet_idx on public.executions(projet_id);
create index if not exists executions_fournisseur_idx on public.executions(fournisseur_id);

-- ------------------------------------------------------------------ releves (1 ligne = 1 produit relevé, format fixe)
create table if not exists public.releves (
  id                uuid primary key default gen_random_uuid(),
  created_at        timestamptz not null default now(),
  execution_id      uuid not null references public.executions(id) on delete cascade,
  besoin_id         text,
  produit_demande   text,                        -- ce qu'on a demandé à l'agent
  produit           text,                        -- ce que l'agent a trouvé
  prix_eur          numeric,
  unite             text,                        -- 'pièce', 'pot 10 L', 'm²', 'paquet 2,2 m²'…
  stock             text,                        -- texte affiché
  en_stock          boolean,
  delai_texte       text,
  delai_jours       int,
  lien              text,
  image_url         text,
  largeur_mm        numeric,
  profondeur_mm     numeric,
  hauteur_mm        numeric,
  valide            boolean,                     -- verdict du CODE
  raisons           jsonb
);
create index if not exists releves_execution_idx on public.releves(execution_id);

-- ------------------------------------------------------------------ modeles_3d (cache : 1 produit = 1 fichier 3D)
create table if not exists public.modeles_3d (
  produit_lien  text primary key,
  glb_url       text not null,
  modele        text,                            -- 'TRELLIS v1', 'TRELLIS.2', 'Hunyuan3D-2'
  duree_s       numeric,
  created_at    timestamptz not null default now()
);

-- ------------------------------------------------------------------ essais (grille des essais de modèles, H et Hugging Face)
create table if not exists public.essais (
  id               uuid primary key default gen_random_uuid(),
  created_at       timestamptz not null default now(),
  tache            text not null,                -- 'relevé de prix', 'guide de travaux', 'lecture photo', 'image → 3D', 'insertion photo'…
  plateforme       text not null,                -- 'H Company', 'Hugging Face Inference Providers', 'Hugging Face Spaces (ZeroGPU)'
  modele           text not null,
  demande          text,                         -- ce qu'on a demandé
  utilisable       boolean,
  duree_s          numeric,
  cout             text,                         -- crédits H, $ HF, ou 'quota gratuit'
  ce_qui_est_faux  text,
  capture_url      text,
  note_sur_5       int check (note_sur_5 between 0 and 5),
  details          jsonb
);

-- ------------------------------------------------------------------ grille de comparaison des agents
create or replace view public.grille_agents with (security_invoker = true) as
select e.created_at, e.fournisseur_id, e.agent, s.nom as skill,
       e.nb_produits_corrects, e.nb_produits_attendus,
       e.duree_s, e.etapes, e.cout_credits, e.format_respecte, e.statut, e.live_url
from public.executions e left join public.skills s on s.id = e.skill_id
order by e.created_at desc;

-- ------------------------------------------------------------------ sécurité (RLS)
-- Le back (et n8n) écrivent avec la clé service_role, qui passe outre la RLS : jamais dans le front ni dans le repo.
-- Le front (clé anon) peut seulement LIRE les tables non personnelles.
alter table public.fournisseurs enable row level security;
alter table public.skills       enable row level security;
alter table public.projets      enable row level security;
alter table public.executions   enable row level security;
alter table public.releves      enable row level security;
alter table public.modeles_3d   enable row level security;
alter table public.essais       enable row level security;
do $$ begin
  create policy "lecture publique" on public.fournisseurs for select using (true);
  create policy "lecture publique" on public.skills       for select using (true);
  create policy "lecture publique" on public.executions   for select using (true);
  create policy "lecture publique" on public.releves      for select using (true);
  create policy "lecture publique" on public.modeles_3d   for select using (true);
  create policy "lecture publique" on public.essais       for select using (true);
exception when duplicate_object then null; end $$;

-- ------------------------------------------------------------------ données de départ (nos tests du 17/11)
insert into public.fournisseurs (id, nom, url, accessible, obstacle, teste_le, notes) values
  ('castorama',   'Castorama',    'https://www.castorama.fr',    true,  null, '2026-11-17', 'Prix, dimensions, stock magasin et délai trouvés. 72 s, 13 étapes.'),
  ('ikea',        'IKEA',         'https://www.ikea.com/fr/fr/', true,  null, '2026-11-17', 'Délai de livraison visible seulement au panier. Pas de peinture murale.'),
  ('bricorama',   'Bricorama',    'https://www.bricorama.fr',    true,  'délai visible seulement au panier', '2026-11-17', 'Partiel. 138 s, 33 étapes.'),
  ('leroymerlin', 'Leroy Merlin', 'https://www.leroymerlin.fr',  false, 'CAPTCHA slider dès l''accueil', '2026-11-17', 'L''agent s''arrête sans contourner.'),
  ('manomano',    'ManoMano',     'https://www.manomano.fr',     false, 'CAPTCHA Cloudflare dès l''accueil', '2026-11-17', 'L''agent s''arrête sans contourner.')
on conflict (id) do nothing;

insert into public.skills (nom, description, agent, consigne, schema_sortie, max_steps, max_time_s) values
('test_acces',
 'Tester si l''agent peut utiliser un site : chercher un produit, relever prix, dimensions, stock magasin, délai.',
 'h/web-surfer-flash',
 'Consigne de test_enseignes.py (TACHE) : ouvrir le site, gérer les cookies, chercher le produit, relever prix, dimensions, délai de livraison et stock du magasin le plus proche ; s''arrêter sur CAPTCHA.',
 '{"acces_site":"ok|partiel|bloque","obstacle":"texte|null","produit":"texte","url_produit":"url","prix_eur":0,"dimensions":"texte","magasin":"texte","stock_magasin":"texte","delai_livraison":"texte","commentaire":"texte"}'::jsonb,
 40, 600),
('releve_prix',
 'Relever prix, unité, stock, délai et lien de N produits chez un fournisseur (format fixe).',
 'h/web-surfer-flash',
 'Tu relèves des prix sur {url}. Code postal : {code_postal}. Ne crée pas de compte, ne te connecte pas, ne paie rien. Tu peux ajouter au panier pour voir le délai de livraison mais arrête-toi au panier. Si tu tombes sur un CAPTCHA ou une page "accès refusé", ne le contourne pas : arrête-toi et réponds avec acces_site = bloque.
Pour CHAQUE produit de la liste, cherche-le, ouvre la fiche du produit le plus proche vendu par l''enseigne et relève tel qu''affiché : nom exact, prix TTC, unité de vente, disponibilité en stock dans le magasin le plus proche de {code_postal} (texte affiché), délai de livraison (texte + nombre de jours), lien de la fiche.
Ne devine jamais une valeur : si elle n''est pas affichée, laisse le champ vide.
PRODUITS :
{produits}',
 '{"acces_site":"ok|partiel|bloque","obstacle":"texte|null","produits":[{"produit_demande":"texte","produit":"texte","prix_eur":0,"unite":"texte","stock":"texte","en_stock":true,"delai_texte":"texte","delai_jours":0,"lien":"url"}],"commentaire":"texte"}'::jsonb,
 120, 1200),
('parcours_marcel',
 'Parcours complet Marcel : candidats par besoin, vérification des dimensions par le code, panier sans paiement.',
 'h/web-surfer-flash',
 'Consigne générée par marcel_core/agents.py (consigne(projet, url)) à partir des besoins du projet.',
 '{"acces_site":"ok|partiel|bloque","produits":[{"besoin_id":"texte","nom":"texte","url":"url","prix_eur":0,"largeur_mm":0,"profondeur_mm":0,"hauteur_mm":0,"en_stock_magasin":true,"stock_texte":"texte","delai_livraison_jours":0}],"commentaire":"texte"}'::jsonb,
 150, 1500)
on conflict (nom) do nothing;

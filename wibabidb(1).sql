-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1
-- Généré le : dim. 19 avr. 2026 à 18:44
-- Version du serveur : 10.4.32-MariaDB
-- Version de PHP : 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `wibabidb`
--

-- --------------------------------------------------------

--
-- Structure de la table `auth_group`
--

CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL,
  `name` varchar(150) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `auth_group_permissions`
--

CREATE TABLE `auth_group_permissions` (
  `id` bigint(20) NOT NULL,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `auth_permission`
--

CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `auth_permission`
--

INSERT INTO `auth_permission` (`id`, `name`, `content_type_id`, `codename`) VALUES
(1, 'Can add log entry', 1, 'add_logentry'),
(2, 'Can change log entry', 1, 'change_logentry'),
(3, 'Can delete log entry', 1, 'delete_logentry'),
(4, 'Can view log entry', 1, 'view_logentry'),
(5, 'Can add permission', 2, 'add_permission'),
(6, 'Can change permission', 2, 'change_permission'),
(7, 'Can delete permission', 2, 'delete_permission'),
(8, 'Can view permission', 2, 'view_permission'),
(9, 'Can add group', 3, 'add_group'),
(10, 'Can change group', 3, 'change_group'),
(11, 'Can delete group', 3, 'delete_group'),
(12, 'Can view group', 3, 'view_group'),
(13, 'Can add content type', 4, 'add_contenttype'),
(14, 'Can change content type', 4, 'change_contenttype'),
(15, 'Can delete content type', 4, 'delete_contenttype'),
(16, 'Can view content type', 4, 'view_contenttype'),
(17, 'Can add session', 5, 'add_session'),
(18, 'Can change session', 5, 'change_session'),
(19, 'Can delete session', 5, 'delete_session'),
(20, 'Can view session', 5, 'view_session'),
(21, 'Can add Société', 6, 'add_societe'),
(22, 'Can change Société', 6, 'change_societe'),
(23, 'Can delete Société', 6, 'delete_societe'),
(24, 'Can view Société', 6, 'view_societe'),
(25, 'Can add Utilisateur', 7, 'add_utilisateur'),
(26, 'Can change Utilisateur', 7, 'change_utilisateur'),
(27, 'Can delete Utilisateur', 7, 'delete_utilisateur'),
(28, 'Can view Utilisateur', 7, 'view_utilisateur'),
(29, 'Can add Backup', 8, 'add_backup'),
(30, 'Can change Backup', 8, 'change_backup'),
(31, 'Can delete Backup', 8, 'delete_backup'),
(32, 'Can view Backup', 8, 'view_backup'),
(33, 'Can add Clé d\'activation', 9, 'add_cleactivation'),
(34, 'Can change Clé d\'activation', 9, 'change_cleactivation'),
(35, 'Can delete Clé d\'activation', 9, 'delete_cleactivation'),
(36, 'Can view Clé d\'activation', 9, 'view_cleactivation'),
(37, 'Can add audit cle', 10, 'add_auditcle'),
(38, 'Can change audit cle', 10, 'change_auditcle'),
(39, 'Can delete audit cle', 10, 'delete_auditcle'),
(40, 'Can view audit cle', 10, 'view_auditcle'),
(41, 'Can add Historique de connexion', 11, 'add_historiqueconnexion'),
(42, 'Can change Historique de connexion', 11, 'change_historiqueconnexion'),
(43, 'Can delete Historique de connexion', 11, 'delete_historiqueconnexion'),
(44, 'Can view Historique de connexion', 11, 'view_historiqueconnexion'),
(45, 'Can add Catégorie', 12, 'add_categorie'),
(46, 'Can change Catégorie', 12, 'change_categorie'),
(47, 'Can delete Catégorie', 12, 'delete_categorie'),
(48, 'Can view Catégorie', 12, 'view_categorie'),
(49, 'Can add Type de client', 13, 'add_typeclient'),
(50, 'Can change Type de client', 13, 'change_typeclient'),
(51, 'Can delete Type de client', 13, 'delete_typeclient'),
(52, 'Can view Type de client', 13, 'view_typeclient'),
(53, 'Can add Client', 14, 'add_client'),
(54, 'Can change Client', 14, 'change_client'),
(55, 'Can delete Client', 14, 'delete_client'),
(56, 'Can view Client', 14, 'view_client'),
(57, 'Can add Taux TVA', 15, 'add_taux'),
(58, 'Can change Taux TVA', 15, 'change_taux'),
(59, 'Can delete Taux TVA', 15, 'delete_taux'),
(60, 'Can view Taux TVA', 15, 'view_taux'),
(61, 'Can add Fournisseur', 16, 'add_fournisseur'),
(62, 'Can change Fournisseur', 16, 'change_fournisseur'),
(63, 'Can delete Fournisseur', 16, 'delete_fournisseur'),
(64, 'Can view Fournisseur', 16, 'view_fournisseur'),
(65, 'Can add Produit', 17, 'add_produit'),
(66, 'Can change Produit', 17, 'change_produit'),
(67, 'Can delete Produit', 17, 'delete_produit'),
(68, 'Can view Produit', 17, 'view_produit'),
(69, 'Can add Service', 18, 'add_service'),
(70, 'Can change Service', 18, 'change_service'),
(71, 'Can delete Service', 18, 'delete_service'),
(72, 'Can view Service', 18, 'view_service'),
(73, 'Can add Entrée stock', 19, 'add_entreestock'),
(74, 'Can change Entrée stock', 19, 'change_entreestock'),
(75, 'Can delete Entrée stock', 19, 'delete_entreestock'),
(76, 'Can view Entrée stock', 19, 'view_entreestock'),
(77, 'Can add Sortie stock', 20, 'add_sortiestock'),
(78, 'Can change Sortie stock', 20, 'change_sortiestock'),
(79, 'Can delete Sortie stock', 20, 'delete_sortiestock'),
(80, 'Can view Sortie stock', 20, 'view_sortiestock'),
(81, 'Can add ligne facture', 21, 'add_lignefacture'),
(82, 'Can change ligne facture', 21, 'change_lignefacture'),
(83, 'Can delete ligne facture', 21, 'delete_lignefacture'),
(84, 'Can view ligne facture', 21, 'view_lignefacture'),
(85, 'Can add Facture', 22, 'add_facture'),
(86, 'Can change Facture', 22, 'change_facture'),
(87, 'Can delete Facture', 22, 'delete_facture'),
(88, 'Can view Facture', 22, 'view_facture'),
(89, 'Can add Facture en attente OBR', 23, 'add_facturependingobr'),
(90, 'Can change Facture en attente OBR', 23, 'change_facturependingobr'),
(91, 'Can delete Facture en attente OBR', 23, 'delete_facturependingobr'),
(92, 'Can view Facture en attente OBR', 23, 'view_facturependingobr'),
(93, 'Can add Rapport', 24, 'add_rapport'),
(94, 'Can change Rapport', 24, 'change_rapport'),
(95, 'Can delete Rapport', 24, 'delete_rapport'),
(96, 'Can view Rapport', 24, 'view_rapport');

-- --------------------------------------------------------

--
-- Structure de la table `categories_categorie`
--

CREATE TABLE `categories_categorie` (
  `id` bigint(20) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `description` longtext NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `societe_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `clients_client`
--

CREATE TABLE `clients_client` (
  `id` bigint(20) NOT NULL,
  `nom` varchar(150) NOT NULL,
  `nif` varchar(50) DEFAULT NULL,
  `assujeti_tva` tinyint(1) NOT NULL,
  `adresse` varchar(200) DEFAULT NULL,
  `date_creation` datetime(6) NOT NULL,
  `societe_id` bigint(20) NOT NULL,
  `type_client_id` bigint(20) DEFAULT NULL,
  `avenue` varchar(100) DEFAULT NULL,
  `commune` varchar(100) DEFAULT NULL,
  `cree_par_id` bigint(20) DEFAULT NULL,
  `date_verification` datetime(6) DEFAULT NULL,
  `nom_obr_officiel` varchar(150) DEFAULT NULL,
  `province` varchar(100) DEFAULT NULL,
  `quartier` varchar(100) DEFAULT NULL,
  `telephone` varchar(30) DEFAULT NULL,
  `verifie_obr` tinyint(1) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `numero` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `clients_typeclient`
--

CREATE TABLE `clients_typeclient` (
  `id` bigint(20) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `societe_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `django_admin_log`
--

CREATE TABLE `django_admin_log` (
  `id` int(11) NOT NULL,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext DEFAULT NULL,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint(5) UNSIGNED NOT NULL CHECK (`action_flag` >= 0),
  `change_message` longtext NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `django_content_type`
--

CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `django_content_type`
--

INSERT INTO `django_content_type` (`id`, `app_label`, `model`) VALUES
(1, 'admin', 'logentry'),
(3, 'auth', 'group'),
(2, 'auth', 'permission'),
(12, 'categories', 'categorie'),
(14, 'clients', 'client'),
(13, 'clients', 'typeclient'),
(4, 'contenttypes', 'contenttype'),
(22, 'facturer', 'facture'),
(23, 'facturer', 'facturependingobr'),
(21, 'facturer', 'lignefacture'),
(16, 'fournisseurs', 'fournisseur'),
(17, 'produits', 'produit'),
(24, 'rapports', 'rapport'),
(18, 'services', 'service'),
(5, 'sessions', 'session'),
(6, 'societe', 'societe'),
(19, 'stock', 'entreestock'),
(20, 'stock', 'sortiestock'),
(10, 'superadmin', 'auditcle'),
(8, 'superadmin', 'backup'),
(9, 'superadmin', 'cleactivation'),
(11, 'superadmin', 'historiqueconnexion'),
(7, 'superadmin', 'utilisateur'),
(15, 'taux', 'taux');

-- --------------------------------------------------------

--
-- Structure de la table `django_migrations`
--

CREATE TABLE `django_migrations` (
  `id` bigint(20) NOT NULL,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `django_migrations`
--

INSERT INTO `django_migrations` (`id`, `app`, `name`, `applied`) VALUES
(1, 'societe', '0001_initial', '2026-04-18 19:06:31.821035'),
(2, 'contenttypes', '0001_initial', '2026-04-18 19:06:32.638434'),
(3, 'contenttypes', '0002_remove_content_type_name', '2026-04-18 19:06:33.441198'),
(4, 'auth', '0001_initial', '2026-04-18 19:06:36.958999'),
(5, 'auth', '0002_alter_permission_name_max_length', '2026-04-18 19:06:38.638526'),
(6, 'auth', '0003_alter_user_email_max_length', '2026-04-18 19:06:38.690601'),
(7, 'auth', '0004_alter_user_username_opts', '2026-04-18 19:06:38.739611'),
(8, 'auth', '0005_alter_user_last_login_null', '2026-04-18 19:06:38.792106'),
(9, 'auth', '0006_require_contenttypes_0002', '2026-04-18 19:06:38.837434'),
(10, 'auth', '0007_alter_validators_add_error_messages', '2026-04-18 19:06:38.888824'),
(11, 'auth', '0008_alter_user_username_max_length', '2026-04-18 19:06:39.143540'),
(12, 'auth', '0009_alter_user_last_name_max_length', '2026-04-18 19:06:39.182082'),
(13, 'auth', '0010_alter_group_name_max_length', '2026-04-18 19:06:39.389086'),
(14, 'auth', '0011_update_proxy_permissions', '2026-04-18 19:06:39.455066'),
(15, 'auth', '0012_alter_user_first_name_max_length', '2026-04-18 19:06:39.503643'),
(16, 'superadmin', '0001_initial', '2026-04-18 19:06:53.742780'),
(17, 'admin', '0001_initial', '2026-04-18 19:06:57.621069'),
(18, 'admin', '0002_logentry_remove_auto_add', '2026-04-18 19:06:57.785799'),
(19, 'admin', '0003_logentry_add_action_flag_choices', '2026-04-18 19:06:57.867997'),
(20, 'categories', '0001_initial', '2026-04-18 19:06:59.477580'),
(21, 'societe', '0002_societe_forme_societe_secteur', '2026-04-18 19:06:59.877435'),
(22, 'societe', '0003_add_logo_field', '2026-04-18 19:07:00.079798'),
(23, 'societe', '0004_remove_societe_logo', '2026-04-18 19:07:00.355756'),
(24, 'societe', '0005_societe_logo', '2026-04-18 19:07:00.684457'),
(25, 'societe', '0006_societe_nom_complet_gerant_societe_numero_depart', '2026-04-18 19:07:01.074266'),
(26, 'societe', '0007_societe_email_societe', '2026-04-18 19:07:02.141697'),
(27, 'clients', '0001_initial', '2026-04-18 19:07:08.149672'),
(28, 'clients', '0002_client_avenue_client_commune_client_cree_par_and_more', '2026-04-18 19:07:13.130241'),
(29, 'clients', '0003_alter_client_unique_together_and_more', '2026-04-18 19:07:18.464880'),
(30, 'taux', '0001_initial', '2026-04-18 19:07:20.117720'),
(31, 'services', '0001_initial', '2026-04-18 19:07:22.832934'),
(32, 'produits', '0001_initial', '2026-04-18 19:07:26.106632'),
(33, 'facturer', '0001_initial', '2026-04-18 19:07:27.618703'),
(34, 'facturer', '0002_initial', '2026-04-18 19:07:34.825759'),
(35, 'facturer', '0003_facturependingobr', '2026-04-18 19:07:36.197821'),
(36, 'facturer', '0004_facturependingobr_payload', '2026-04-18 19:07:36.473893'),
(37, 'facturer', '0005_facture_invoice_identifier_alter_facture_numero', '2026-04-18 19:07:36.895678'),
(38, 'facturer', '0006_rename_signature_obr_facture_electronic_signature_and_more', '2026-04-18 19:07:42.710950'),
(39, 'facturer', '0007_alter_facture_cree_par_alter_facture_date_creation_and_more', '2026-04-18 19:07:43.437643'),
(40, 'facturer', '0008_alter_facture_unique_together_alter_facture_numero_and_more', '2026-04-18 19:07:44.645638'),
(41, 'facturer', '0009_facture_date_annulation', '2026-04-18 19:07:44.769665'),
(42, 'fournisseurs', '0001_initial', '2026-04-18 19:07:46.231058'),
(43, 'produits', '0002_alter_produit_code_alter_produit_date_creation_and_more', '2026-04-18 19:07:51.933740'),
(44, 'produits', '0003_alter_produit_options_alter_produit_prix_vente', '2026-04-18 19:07:52.084689'),
(45, 'produits', '0004_alter_produit_origine', '2026-04-18 19:07:52.140846'),
(46, 'rapports', '0001_initial', '2026-04-18 19:07:52.366369'),
(47, 'rapports', '0002_initial', '2026-04-18 19:07:55.837754'),
(48, 'sessions', '0001_initial', '2026-04-18 19:07:56.922417'),
(49, 'societe', '0008_societe_assujeti_pfl_alter_societe_assujeti_tc_and_more', '2026-04-18 19:07:58.860893'),
(50, 'stock', '0001_initial', '2026-04-18 19:08:05.756534'),
(51, 'stock', '0002_entreestock_commentaire_entreestock_facture', '2026-04-18 19:08:07.112468'),
(52, 'stock', '0003_sortiestock_facture', '2026-04-18 19:08:08.924376'),
(53, 'stock', '0004_alter_entreestock_unique_together_and_more', '2026-04-18 19:08:12.379369');

-- --------------------------------------------------------

--
-- Structure de la table `django_session`
--

CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `django_session`
--

INSERT INTO `django_session` (`session_key`, `session_data`, `expire_date`) VALUES
('2z1m86nhfnon2o1c8nyhvhtik3iz3o88', '.eJxVjEEOwiAQRe_C2pCOiMUu3XsGMsMMFjVgoE00xrtrky50-9_776U8ztPo5ybVJ1aDArX53QjDVfIC-IL5XHQoeaqJ9KLolTZ9Kiy34-r-BUZs4_dt2SI7sQwUdxhEgMnG3h5cNAGj6fq9YXAGiWTbATmOIQIwW7Ah9rREm7SWSvbyuKf6VEP3_gDmzUC0:1wEVEH:92_fHa-XdSGE2XHS01kD0bslDMXibzSCBmdw4xCNAbg', '2026-04-20 00:42:41.252064');

-- --------------------------------------------------------

--
-- Structure de la table `facturer_facture`
--

CREATE TABLE `facturer_facture` (
  `id` bigint(20) NOT NULL,
  `numero` varchar(50) NOT NULL,
  `date_facture` date NOT NULL,
  `heure_facture` time(6) NOT NULL,
  `type_facture` varchar(5) NOT NULL,
  `bon_commande` varchar(100) DEFAULT NULL,
  `devise` varchar(5) NOT NULL,
  `mode_paiement` varchar(10) NOT NULL,
  `total_ht` decimal(14,2) NOT NULL,
  `total_tva` decimal(14,2) NOT NULL,
  `total_ttc` decimal(14,2) NOT NULL,
  `statut_obr` varchar(20) NOT NULL,
  `message_obr` longtext NOT NULL,
  `date_envoi_obr` datetime(6) DEFAULT NULL,
  `electronic_signature` longtext NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `client_id` bigint(20) NOT NULL,
  `cree_par_id` bigint(20) DEFAULT NULL,
  `societe_id` bigint(20) NOT NULL,
  `invoice_identifier` varchar(150) DEFAULT NULL,
  `facture_originale_id` bigint(20) DEFAULT NULL,
  `motif_avoir` varchar(150) NOT NULL,
  `obr_registered_date` datetime(6) DEFAULT NULL,
  `obr_registered_number` varchar(50) DEFAULT NULL,
  `qr_code_image` varchar(100) DEFAULT NULL,
  `date_annulation` datetime(6) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `facturer_facturependingobr`
--

CREATE TABLE `facturer_facturependingobr` (
  `id` bigint(20) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `statut` varchar(50) NOT NULL,
  `message` longtext DEFAULT NULL,
  `facture_id` bigint(20) NOT NULL,
  `payload` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`payload`)),
  `retry_count` int(10) UNSIGNED NOT NULL CHECK (`retry_count` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `facturer_lignefacture`
--

CREATE TABLE `facturer_lignefacture` (
  `id` bigint(20) NOT NULL,
  `designation` varchar(250) NOT NULL,
  `quantite_stock` decimal(10,2) NOT NULL,
  `taux_tva` decimal(5,2) NOT NULL,
  `prix_vente_tvac` decimal(12,2) NOT NULL,
  `quantite` decimal(10,2) NOT NULL,
  `facture_id` bigint(20) NOT NULL,
  `produit_id` bigint(20) DEFAULT NULL,
  `service_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `fournisseurs_fournisseur`
--

CREATE TABLE `fournisseurs_fournisseur` (
  `id` bigint(20) NOT NULL,
  `nom` varchar(150) NOT NULL,
  `adresse` varchar(250) NOT NULL,
  `telephone` varchar(20) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `societe_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `produits_produit`
--

CREATE TABLE `produits_produit` (
  `id` bigint(20) NOT NULL,
  `code` varchar(50) NOT NULL,
  `designation` varchar(200) NOT NULL,
  `unite` varchar(50) NOT NULL,
  `prix_vente` decimal(12,2) NOT NULL,
  `devise` varchar(10) NOT NULL,
  `origine` varchar(10) NOT NULL,
  `statut` varchar(20) NOT NULL,
  `reference_dmc` varchar(100) NOT NULL,
  `rubrique_tarifaire` varchar(50) NOT NULL,
  `nombre_par_paquet` int(10) UNSIGNED DEFAULT NULL,
  `description_paquet` varchar(150) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `categorie_id` bigint(20) NOT NULL,
  `societe_id` bigint(20) NOT NULL,
  `taux_tva_id` bigint(20) DEFAULT NULL
) ;

-- --------------------------------------------------------

--
-- Structure de la table `rapports_rapport`
--

CREATE TABLE `rapports_rapport` (
  `id` bigint(20) NOT NULL,
  `type_rapport` varchar(30) NOT NULL,
  `date_debut` date DEFAULT NULL,
  `date_fin` date DEFAULT NULL,
  `fichier_pdf` varchar(100) DEFAULT NULL,
  `fichier_excel` varchar(100) DEFAULT NULL,
  `date_creation` datetime(6) NOT NULL,
  `cree_par_id` bigint(20) DEFAULT NULL,
  `societe_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `services_service`
--

CREATE TABLE `services_service` (
  `id` bigint(20) NOT NULL,
  `designation` varchar(200) NOT NULL,
  `prix_vente` decimal(10,2) NOT NULL,
  `statut` varchar(10) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `societe_id` bigint(20) NOT NULL,
  `taux_tva_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `societe_societe`
--

CREATE TABLE `societe_societe` (
  `id` bigint(20) NOT NULL,
  `nom` varchar(200) NOT NULL,
  `nif` varchar(50) NOT NULL,
  `registre` varchar(100) NOT NULL,
  `boite_postal` varchar(50) DEFAULT NULL,
  `telephone` varchar(50) NOT NULL,
  `province` varchar(100) NOT NULL,
  `commune` varchar(100) NOT NULL,
  `quartier` varchar(100) NOT NULL,
  `avenue` varchar(150) NOT NULL,
  `numero` varchar(20) DEFAULT NULL,
  `centre_fiscale` varchar(10) NOT NULL,
  `assujeti_tva` tinyint(1) NOT NULL,
  `assujeti_tc` tinyint(1) NOT NULL,
  `obr_username` varchar(100) NOT NULL,
  `obr_password` varchar(100) NOT NULL,
  `obr_system_id` varchar(100) NOT NULL,
  `obr_actif` tinyint(1) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `forme` varchar(50) NOT NULL,
  `secteur` varchar(250) NOT NULL,
  `logo` varchar(100) DEFAULT NULL,
  `nom_complet_gerant` varchar(200) NOT NULL,
  `numero_depart` int(10) UNSIGNED NOT NULL CHECK (`numero_depart` >= 0),
  `email_societe` varchar(254) NOT NULL,
  `assujeti_pfl` tinyint(1) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `stock_entreestock`
--

CREATE TABLE `stock_entreestock` (
  `id` bigint(20) NOT NULL,
  `type_entree` varchar(5) NOT NULL,
  `numero_ref` varchar(50) NOT NULL,
  `date_entree` date NOT NULL,
  `quantite` decimal(10,2) NOT NULL,
  `prix_revient` decimal(12,2) NOT NULL,
  `prix_vente_actuel` decimal(12,2) NOT NULL,
  `statut_obr` varchar(20) NOT NULL,
  `message_obr` longtext NOT NULL,
  `date_envoi_obr` datetime(6) DEFAULT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `fournisseur_id` bigint(20) DEFAULT NULL,
  `produit_id` bigint(20) NOT NULL,
  `societe_id` bigint(20) NOT NULL,
  `commentaire` longtext DEFAULT NULL,
  `facture_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `stock_sortiestock`
--

CREATE TABLE `stock_sortiestock` (
  `id` bigint(20) NOT NULL,
  `type_sortie` varchar(5) NOT NULL,
  `code` varchar(50) NOT NULL,
  `date_sortie` date NOT NULL,
  `quantite` decimal(10,2) NOT NULL,
  `prix` decimal(12,2) NOT NULL,
  `commentaire` longtext NOT NULL,
  `statut_obr` varchar(20) NOT NULL,
  `message_obr` longtext NOT NULL,
  `date_envoi_obr` datetime(6) DEFAULT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `entree_stock_id` bigint(20) NOT NULL,
  `societe_id` bigint(20) NOT NULL,
  `facture_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_auditcle`
--

CREATE TABLE `superadmin_auditcle` (
  `id` bigint(20) NOT NULL,
  `action` varchar(20) NOT NULL,
  `message` longtext NOT NULL,
  `ip_address` char(39) DEFAULT NULL,
  `date_action` datetime(6) NOT NULL,
  `societe_id` bigint(20) DEFAULT NULL,
  `cle_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_backup`
--

CREATE TABLE `superadmin_backup` (
  `id` bigint(20) NOT NULL,
  `date_backup` datetime(6) NOT NULL,
  `type_backup` varchar(20) NOT NULL,
  `fichier` varchar(100) DEFAULT NULL,
  `taille_fichier` bigint(20) DEFAULT NULL,
  `succes` tinyint(1) NOT NULL,
  `message` longtext NOT NULL,
  `effectue_par_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_cleactivation`
--

CREATE TABLE `superadmin_cleactivation` (
  `id` bigint(20) NOT NULL,
  `cle_visible` varchar(50) NOT NULL,
  `empreinte_hmac` varchar(64) NOT NULL,
  `type_plan` varchar(20) NOT NULL,
  `duree_mois` smallint(5) UNSIGNED NOT NULL CHECK (`duree_mois` >= 0),
  `statut` varchar(20) NOT NULL,
  `date_debut` datetime(6) NOT NULL,
  `date_fin` datetime(6) DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `utilisee` tinyint(1) NOT NULL,
  `date_utilisation` datetime(6) DEFAULT NULL,
  `cree_par` varchar(100) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `date_modification` datetime(6) NOT NULL,
  `motif_revocation` longtext NOT NULL,
  `notes` longtext DEFAULT NULL,
  `societe_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_historiqueconnexion`
--

CREATE TABLE `superadmin_historiqueconnexion` (
  `id` bigint(20) NOT NULL,
  `date_connexion` datetime(6) NOT NULL,
  `date_deconnexion` datetime(6) DEFAULT NULL,
  `adresse_ip` char(39) DEFAULT NULL,
  `user_agent` longtext NOT NULL,
  `utilisateur_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `superadmin_historiqueconnexion`
--

INSERT INTO `superadmin_historiqueconnexion` (`id`, `date_connexion`, `date_deconnexion`, `adresse_ip`, `user_agent`, `utilisateur_id`) VALUES
(1, '2026-04-19 16:42:41.074930', NULL, '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0', 1);

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_utilisateur`
--

CREATE TABLE `superadmin_utilisateur` (
  `id` bigint(20) NOT NULL,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `postnom` varchar(100) NOT NULL,
  `prenom` varchar(100) NOT NULL,
  `type_poste` varchar(20) NOT NULL,
  `photo` varchar(100) DEFAULT NULL,
  `droit_stock_categorie` tinyint(1) NOT NULL,
  `droit_stock_produit` tinyint(1) NOT NULL,
  `droit_stock_fournisseur` tinyint(1) NOT NULL,
  `droit_stock_entree` tinyint(1) NOT NULL,
  `droit_stock_sortie` tinyint(1) NOT NULL,
  `droit_facture_pnb` tinyint(1) NOT NULL,
  `droit_facture_fdnb` tinyint(1) NOT NULL,
  `droit_facture_particulier` tinyint(1) NOT NULL,
  `droit_devis` tinyint(1) NOT NULL,
  `droit_rapports` tinyint(1) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `actif` tinyint(1) NOT NULL,
  `societe_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `superadmin_utilisateur`
--

INSERT INTO `superadmin_utilisateur` (`id`, `password`, `last_login`, `is_superuser`, `username`, `first_name`, `last_name`, `email`, `is_staff`, `is_active`, `date_joined`, `nom`, `postnom`, `prenom`, `type_poste`, `photo`, `droit_stock_categorie`, `droit_stock_produit`, `droit_stock_fournisseur`, `droit_stock_entree`, `droit_stock_sortie`, `droit_facture_pnb`, `droit_facture_fdnb`, `droit_facture_particulier`, `droit_devis`, `droit_rapports`, `date_creation`, `actif`, `societe_id`) VALUES
(1, 'pbkdf2_sha256$870000$mANFXdPJzDiHxzu64Aptsh$Y+8xNTDcBcEc5+7ubqhEda16SWCuXk/OO40rxqFw3Ng=', '2026-04-19 16:42:40.795641', 1, 'Admin_kevin', '', '', 'kevin.ngenda@gmail.com', 1, 1, '2026-04-19 16:40:16.492124', '', '', '', 'VENDEUR', '', 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, '2026-04-19 16:40:17.644474', 1, NULL);

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_utilisateur_groups`
--

CREATE TABLE `superadmin_utilisateur_groups` (
  `id` bigint(20) NOT NULL,
  `utilisateur_id` bigint(20) NOT NULL,
  `group_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `superadmin_utilisateur_user_permissions`
--

CREATE TABLE `superadmin_utilisateur_user_permissions` (
  `id` bigint(20) NOT NULL,
  `utilisateur_id` bigint(20) NOT NULL,
  `permission_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `taux_taux`
--

CREATE TABLE `taux_taux` (
  `id` bigint(20) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `valeur` decimal(5,2) NOT NULL,
  `date_creation` datetime(6) NOT NULL,
  `societe_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Index pour les tables déchargées
--

--
-- Index pour la table `auth_group`
--
ALTER TABLE `auth_group`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Index pour la table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  ADD KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`);

--
-- Index pour la table `auth_permission`
--
ALTER TABLE `auth_permission`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`);

--
-- Index pour la table `categories_categorie`
--
ALTER TABLE `categories_categorie`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `categories_categorie_societe_id_nom_86e0c527_uniq` (`societe_id`,`nom`);

--
-- Index pour la table `clients_client`
--
ALTER TABLE `clients_client`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `clients_client_societe_id_nif_65da8580_uniq` (`societe_id`,`nif`),
  ADD KEY `clients_client_type_client_id_e6934412_fk_clients_typeclient_id` (`type_client_id`),
  ADD KEY `clients_client_cree_par_id_ff222626_fk_superadmin_utilisateur_id` (`cree_par_id`);

--
-- Index pour la table `clients_typeclient`
--
ALTER TABLE `clients_typeclient`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `clients_typeclient_societe_id_nom_4b087339_uniq` (`societe_id`,`nom`);

--
-- Index pour la table `django_admin_log`
--
ALTER TABLE `django_admin_log`
  ADD PRIMARY KEY (`id`),
  ADD KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  ADD KEY `django_admin_log_user_id_c564eba6_fk_superadmin_utilisateur_id` (`user_id`);

--
-- Index pour la table `django_content_type`
--
ALTER TABLE `django_content_type`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`);

--
-- Index pour la table `django_migrations`
--
ALTER TABLE `django_migrations`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `django_session`
--
ALTER TABLE `django_session`
  ADD PRIMARY KEY (`session_key`),
  ADD KEY `django_session_expire_date_a5c62663` (`expire_date`);

--
-- Index pour la table `facturer_facture`
--
ALTER TABLE `facturer_facture`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `facturer_facture_societe_id_numero_f0441f44_uniq` (`societe_id`,`numero`),
  ADD UNIQUE KEY `facturer_facture_invoice_identifier_b46bbb22_uniq` (`invoice_identifier`),
  ADD KEY `facturer_facture_client_id_4fb023d8_fk_clients_client_id` (`client_id`),
  ADD KEY `facturer_facture_cree_par_id_4c67e72b_fk_superadmi` (`cree_par_id`),
  ADD KEY `facturer_facture_societe_id_926e5ca8` (`societe_id`),
  ADD KEY `facturer_facture_facture_originale_id_ee697e38_fk_facturer_` (`facture_originale_id`),
  ADD KEY `facturer_fa_societe_ecdbce_idx` (`societe_id`,`type_facture`,`date_facture`);

--
-- Index pour la table `facturer_facturependingobr`
--
ALTER TABLE `facturer_facturependingobr`
  ADD PRIMARY KEY (`id`),
  ADD KEY `facturer_facturepend_facture_id_fb822627_fk_facturer_` (`facture_id`);

--
-- Index pour la table `facturer_lignefacture`
--
ALTER TABLE `facturer_lignefacture`
  ADD PRIMARY KEY (`id`),
  ADD KEY `facturer_lignefacture_facture_id_23a16d2a_fk_facturer_facture_id` (`facture_id`),
  ADD KEY `facturer_lignefacture_produit_id_5d4b7e92_fk_produits_produit_id` (`produit_id`),
  ADD KEY `facturer_lignefacture_service_id_0a542743_fk_services_service_id` (`service_id`);

--
-- Index pour la table `fournisseurs_fournisseur`
--
ALTER TABLE `fournisseurs_fournisseur`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `fournisseurs_fournisseur_societe_id_nom_1160da94_uniq` (`societe_id`,`nom`);

--
-- Index pour la table `produits_produit`
--
ALTER TABLE `produits_produit`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `produits_produit_societe_id_code_a0fa2417_uniq` (`societe_id`,`code`),
  ADD KEY `produits_produit_categorie_id_857419d4_fk_categorie` (`categorie_id`),
  ADD KEY `produits_produit_taux_tva_id_d24dbaee_fk_taux_taux_id` (`taux_tva_id`),
  ADD KEY `produits_pr_societe_c64d9a_idx` (`societe_id`,`code`),
  ADD KEY `produits_pr_societe_ff22c1_idx` (`societe_id`,`origine`),
  ADD KEY `produits_pr_referen_d062f4_idx` (`reference_dmc`);

--
-- Index pour la table `rapports_rapport`
--
ALTER TABLE `rapports_rapport`
  ADD PRIMARY KEY (`id`),
  ADD KEY `rapports_rapport_cree_par_id_a0b0f1d1_fk_superadmi` (`cree_par_id`),
  ADD KEY `rapports_rapport_societe_id_c7af77e6_fk_societe_societe_id` (`societe_id`);

--
-- Index pour la table `services_service`
--
ALTER TABLE `services_service`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `services_service_societe_id_designation_9766a202_uniq` (`societe_id`,`designation`),
  ADD KEY `services_service_taux_tva_id_863d2a69_fk_taux_taux_id` (`taux_tva_id`);

--
-- Index pour la table `societe_societe`
--
ALTER TABLE `societe_societe`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nif` (`nif`);

--
-- Index pour la table `stock_entreestock`
--
ALTER TABLE `stock_entreestock`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `stock_entreestock_societe_id_produit_id_fa_620709d1_uniq` (`societe_id`,`produit_id`,`facture_id`,`type_entree`),
  ADD KEY `stock_entreestock_fournisseur_id_674b5d1e_fk_fournisse` (`fournisseur_id`),
  ADD KEY `stock_entreestock_produit_id_308f972c_fk_produits_produit_id` (`produit_id`),
  ADD KEY `stock_entre_societe_08813f_idx` (`societe_id`,`produit_id`,`date_entree`),
  ADD KEY `stock_entre_statut__470095_idx` (`statut_obr`),
  ADD KEY `stock_entre_facture_04ce08_idx` (`facture_id`);

--
-- Index pour la table `stock_sortiestock`
--
ALTER TABLE `stock_sortiestock`
  ADD PRIMARY KEY (`id`),
  ADD KEY `stock_sortiestock_entree_stock_id_c64407ee_fk_stock_ent` (`entree_stock_id`),
  ADD KEY `stock_sortiestock_societe_id_4234513b_fk_societe_societe_id` (`societe_id`),
  ADD KEY `stock_sortiestock_facture_id_172c9fc5_fk_facturer_facture_id` (`facture_id`);

--
-- Index pour la table `superadmin_auditcle`
--
ALTER TABLE `superadmin_auditcle`
  ADD PRIMARY KEY (`id`),
  ADD KEY `superadmin_auditcle_societe_id_e42d6fce_fk_societe_societe_id` (`societe_id`),
  ADD KEY `superadmin_auditcle_cle_id_2a195cf8_fk_superadmi` (`cle_id`);

--
-- Index pour la table `superadmin_backup`
--
ALTER TABLE `superadmin_backup`
  ADD PRIMARY KEY (`id`),
  ADD KEY `superadmin_backup_effectue_par_id_89dca1ad_fk_superadmi` (`effectue_par_id`);

--
-- Index pour la table `superadmin_cleactivation`
--
ALTER TABLE `superadmin_cleactivation`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `cle_visible` (`cle_visible`),
  ADD KEY `superadmin_cleactiva_societe_id_5fc8db46_fk_societe_s` (`societe_id`);

--
-- Index pour la table `superadmin_historiqueconnexion`
--
ALTER TABLE `superadmin_historiqueconnexion`
  ADD PRIMARY KEY (`id`),
  ADD KEY `superadmin_historiqu_utilisateur_id_616cc67c_fk_superadmi` (`utilisateur_id`);

--
-- Index pour la table `superadmin_utilisateur`
--
ALTER TABLE `superadmin_utilisateur`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD KEY `superadmin_utilisateur_societe_id_eeb00efc_fk_societe_societe_id` (`societe_id`);

--
-- Index pour la table `superadmin_utilisateur_groups`
--
ALTER TABLE `superadmin_utilisateur_groups`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `superadmin_utilisateur_g_utilisateur_id_group_id_8064bbe7_uniq` (`utilisateur_id`,`group_id`),
  ADD KEY `superadmin_utilisateur_groups_group_id_d45bef51_fk_auth_group_id` (`group_id`);

--
-- Index pour la table `superadmin_utilisateur_user_permissions`
--
ALTER TABLE `superadmin_utilisateur_user_permissions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `superadmin_utilisateur_u_utilisateur_id_permissio_9dcaa125_uniq` (`utilisateur_id`,`permission_id`),
  ADD KEY `superadmin_utilisate_permission_id_7ea44f90_fk_auth_perm` (`permission_id`);

--
-- Index pour la table `taux_taux`
--
ALTER TABLE `taux_taux`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `taux_taux_societe_id_nom_00af351f_uniq` (`societe_id`,`nom`);

--
-- AUTO_INCREMENT pour les tables déchargées
--

--
-- AUTO_INCREMENT pour la table `auth_group`
--
ALTER TABLE `auth_group`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `auth_permission`
--
ALTER TABLE `auth_permission`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=97;

--
-- AUTO_INCREMENT pour la table `categories_categorie`
--
ALTER TABLE `categories_categorie`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `clients_client`
--
ALTER TABLE `clients_client`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `clients_typeclient`
--
ALTER TABLE `clients_typeclient`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `django_admin_log`
--
ALTER TABLE `django_admin_log`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `django_content_type`
--
ALTER TABLE `django_content_type`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=25;

--
-- AUTO_INCREMENT pour la table `django_migrations`
--
ALTER TABLE `django_migrations`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=54;

--
-- AUTO_INCREMENT pour la table `facturer_facture`
--
ALTER TABLE `facturer_facture`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `facturer_facturependingobr`
--
ALTER TABLE `facturer_facturependingobr`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `facturer_lignefacture`
--
ALTER TABLE `facturer_lignefacture`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `fournisseurs_fournisseur`
--
ALTER TABLE `fournisseurs_fournisseur`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `produits_produit`
--
ALTER TABLE `produits_produit`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `rapports_rapport`
--
ALTER TABLE `rapports_rapport`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `services_service`
--
ALTER TABLE `services_service`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `societe_societe`
--
ALTER TABLE `societe_societe`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `stock_entreestock`
--
ALTER TABLE `stock_entreestock`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `stock_sortiestock`
--
ALTER TABLE `stock_sortiestock`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `superadmin_auditcle`
--
ALTER TABLE `superadmin_auditcle`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `superadmin_backup`
--
ALTER TABLE `superadmin_backup`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `superadmin_cleactivation`
--
ALTER TABLE `superadmin_cleactivation`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `superadmin_historiqueconnexion`
--
ALTER TABLE `superadmin_historiqueconnexion`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT pour la table `superadmin_utilisateur`
--
ALTER TABLE `superadmin_utilisateur`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT pour la table `superadmin_utilisateur_groups`
--
ALTER TABLE `superadmin_utilisateur_groups`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `superadmin_utilisateur_user_permissions`
--
ALTER TABLE `superadmin_utilisateur_user_permissions`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `taux_taux`
--
ALTER TABLE `taux_taux`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- Contraintes pour les tables déchargées
--

--
-- Contraintes pour la table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  ADD CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  ADD CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);

--
-- Contraintes pour la table `auth_permission`
--
ALTER TABLE `auth_permission`
  ADD CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);

--
-- Contraintes pour la table `categories_categorie`
--
ALTER TABLE `categories_categorie`
  ADD CONSTRAINT `categories_categorie_societe_id_6098daff_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `clients_client`
--
ALTER TABLE `clients_client`
  ADD CONSTRAINT `clients_client_cree_par_id_ff222626_fk_superadmin_utilisateur_id` FOREIGN KEY (`cree_par_id`) REFERENCES `superadmin_utilisateur` (`id`),
  ADD CONSTRAINT `clients_client_societe_id_324daab8_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`),
  ADD CONSTRAINT `clients_client_type_client_id_e6934412_fk_clients_typeclient_id` FOREIGN KEY (`type_client_id`) REFERENCES `clients_typeclient` (`id`);

--
-- Contraintes pour la table `clients_typeclient`
--
ALTER TABLE `clients_typeclient`
  ADD CONSTRAINT `clients_typeclient_societe_id_a0b6a697_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `django_admin_log`
--
ALTER TABLE `django_admin_log`
  ADD CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  ADD CONSTRAINT `django_admin_log_user_id_c564eba6_fk_superadmin_utilisateur_id` FOREIGN KEY (`user_id`) REFERENCES `superadmin_utilisateur` (`id`);

--
-- Contraintes pour la table `facturer_facture`
--
ALTER TABLE `facturer_facture`
  ADD CONSTRAINT `facturer_facture_client_id_4fb023d8_fk_clients_client_id` FOREIGN KEY (`client_id`) REFERENCES `clients_client` (`id`),
  ADD CONSTRAINT `facturer_facture_cree_par_id_4c67e72b_fk_superadmi` FOREIGN KEY (`cree_par_id`) REFERENCES `superadmin_utilisateur` (`id`),
  ADD CONSTRAINT `facturer_facture_facture_originale_id_ee697e38_fk_facturer_` FOREIGN KEY (`facture_originale_id`) REFERENCES `facturer_facture` (`id`),
  ADD CONSTRAINT `facturer_facture_societe_id_926e5ca8_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `facturer_facturependingobr`
--
ALTER TABLE `facturer_facturependingobr`
  ADD CONSTRAINT `facturer_facturepend_facture_id_fb822627_fk_facturer_` FOREIGN KEY (`facture_id`) REFERENCES `facturer_facture` (`id`);

--
-- Contraintes pour la table `facturer_lignefacture`
--
ALTER TABLE `facturer_lignefacture`
  ADD CONSTRAINT `facturer_lignefacture_facture_id_23a16d2a_fk_facturer_facture_id` FOREIGN KEY (`facture_id`) REFERENCES `facturer_facture` (`id`),
  ADD CONSTRAINT `facturer_lignefacture_produit_id_5d4b7e92_fk_produits_produit_id` FOREIGN KEY (`produit_id`) REFERENCES `produits_produit` (`id`),
  ADD CONSTRAINT `facturer_lignefacture_service_id_0a542743_fk_services_service_id` FOREIGN KEY (`service_id`) REFERENCES `services_service` (`id`);

--
-- Contraintes pour la table `fournisseurs_fournisseur`
--
ALTER TABLE `fournisseurs_fournisseur`
  ADD CONSTRAINT `fournisseurs_fournis_societe_id_7f9948f9_fk_societe_s` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `produits_produit`
--
ALTER TABLE `produits_produit`
  ADD CONSTRAINT `produits_produit_categorie_id_857419d4_fk_categorie` FOREIGN KEY (`categorie_id`) REFERENCES `categories_categorie` (`id`),
  ADD CONSTRAINT `produits_produit_societe_id_45bae434_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`),
  ADD CONSTRAINT `produits_produit_taux_tva_id_d24dbaee_fk_taux_taux_id` FOREIGN KEY (`taux_tva_id`) REFERENCES `taux_taux` (`id`);

--
-- Contraintes pour la table `rapports_rapport`
--
ALTER TABLE `rapports_rapport`
  ADD CONSTRAINT `rapports_rapport_cree_par_id_a0b0f1d1_fk_superadmi` FOREIGN KEY (`cree_par_id`) REFERENCES `superadmin_utilisateur` (`id`),
  ADD CONSTRAINT `rapports_rapport_societe_id_c7af77e6_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `services_service`
--
ALTER TABLE `services_service`
  ADD CONSTRAINT `services_service_societe_id_08f25670_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`),
  ADD CONSTRAINT `services_service_taux_tva_id_863d2a69_fk_taux_taux_id` FOREIGN KEY (`taux_tva_id`) REFERENCES `taux_taux` (`id`);

--
-- Contraintes pour la table `stock_entreestock`
--
ALTER TABLE `stock_entreestock`
  ADD CONSTRAINT `stock_entreestock_facture_id_14811000_fk_facturer_facture_id` FOREIGN KEY (`facture_id`) REFERENCES `facturer_facture` (`id`),
  ADD CONSTRAINT `stock_entreestock_fournisseur_id_674b5d1e_fk_fournisse` FOREIGN KEY (`fournisseur_id`) REFERENCES `fournisseurs_fournisseur` (`id`),
  ADD CONSTRAINT `stock_entreestock_produit_id_308f972c_fk_produits_produit_id` FOREIGN KEY (`produit_id`) REFERENCES `produits_produit` (`id`),
  ADD CONSTRAINT `stock_entreestock_societe_id_d8fedc3d_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `stock_sortiestock`
--
ALTER TABLE `stock_sortiestock`
  ADD CONSTRAINT `stock_sortiestock_entree_stock_id_c64407ee_fk_stock_ent` FOREIGN KEY (`entree_stock_id`) REFERENCES `stock_entreestock` (`id`),
  ADD CONSTRAINT `stock_sortiestock_facture_id_172c9fc5_fk_facturer_facture_id` FOREIGN KEY (`facture_id`) REFERENCES `facturer_facture` (`id`),
  ADD CONSTRAINT `stock_sortiestock_societe_id_4234513b_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `superadmin_auditcle`
--
ALTER TABLE `superadmin_auditcle`
  ADD CONSTRAINT `superadmin_auditcle_cle_id_2a195cf8_fk_superadmi` FOREIGN KEY (`cle_id`) REFERENCES `superadmin_cleactivation` (`id`),
  ADD CONSTRAINT `superadmin_auditcle_societe_id_e42d6fce_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `superadmin_backup`
--
ALTER TABLE `superadmin_backup`
  ADD CONSTRAINT `superadmin_backup_effectue_par_id_89dca1ad_fk_superadmi` FOREIGN KEY (`effectue_par_id`) REFERENCES `superadmin_utilisateur` (`id`);

--
-- Contraintes pour la table `superadmin_cleactivation`
--
ALTER TABLE `superadmin_cleactivation`
  ADD CONSTRAINT `superadmin_cleactiva_societe_id_5fc8db46_fk_societe_s` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `superadmin_historiqueconnexion`
--
ALTER TABLE `superadmin_historiqueconnexion`
  ADD CONSTRAINT `superadmin_historiqu_utilisateur_id_616cc67c_fk_superadmi` FOREIGN KEY (`utilisateur_id`) REFERENCES `superadmin_utilisateur` (`id`);

--
-- Contraintes pour la table `superadmin_utilisateur`
--
ALTER TABLE `superadmin_utilisateur`
  ADD CONSTRAINT `superadmin_utilisateur_societe_id_eeb00efc_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);

--
-- Contraintes pour la table `superadmin_utilisateur_groups`
--
ALTER TABLE `superadmin_utilisateur_groups`
  ADD CONSTRAINT `superadmin_utilisate_utilisateur_id_5ff42af4_fk_superadmi` FOREIGN KEY (`utilisateur_id`) REFERENCES `superadmin_utilisateur` (`id`),
  ADD CONSTRAINT `superadmin_utilisateur_groups_group_id_d45bef51_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);

--
-- Contraintes pour la table `superadmin_utilisateur_user_permissions`
--
ALTER TABLE `superadmin_utilisateur_user_permissions`
  ADD CONSTRAINT `superadmin_utilisate_permission_id_7ea44f90_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  ADD CONSTRAINT `superadmin_utilisate_utilisateur_id_d8972572_fk_superadmi` FOREIGN KEY (`utilisateur_id`) REFERENCES `superadmin_utilisateur` (`id`);

--
-- Contraintes pour la table `taux_taux`
--
ALTER TABLE `taux_taux`
  ADD CONSTRAINT `taux_taux_societe_id_4d6bac4c_fk_societe_societe_id` FOREIGN KEY (`societe_id`) REFERENCES `societe_societe` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;

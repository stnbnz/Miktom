-- Create ActivityLog table
CREATE TABLE IF NOT EXISTS `dashboard_activitylog` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `timestamp` datetime(6) NOT NULL,
  `activity_type` varchar(30) NOT NULL,
  `description` longtext NOT NULL,
  `ip_address` varchar(50) NOT NULL,
  `user_agent` longtext NOT NULL,
  `metadata` json NOT NULL DEFAULT (json_object()),
  `success` tinyint(1) NOT NULL DEFAULT 1,
  `error_message` longtext NOT NULL,
  `user` varchar(100) NOT NULL,
  `router_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dashboard_a_activit_idx` (`activity_type`, `timestamp`),
  KEY `dashboard_a_router_idx` (`router_id`, `timestamp`),
  KEY `dashboard_activitylog_router_id` (`router_id`),
  CONSTRAINT `dashboard_activitylog_router_id_fk` 
    FOREIGN KEY (`router_id`) REFERENCES `dashboard_router` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create UserSession table
CREATE TABLE IF NOT EXISTS `dashboard_usersession` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_key` varchar(100) NOT NULL UNIQUE,
  `user` varchar(100) NOT NULL,
  `ip_address` varchar(50) NOT NULL,
  `user_agent` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `last_activity` datetime(6) NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `router_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_key` (`session_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create index on last_activity
CREATE INDEX `dashboard_usersession_last_activity` ON `dashboard_usersession` (`last_activity`);

-- Mark migrations as applied
INSERT IGNORE INTO `django_migrations` (`app`, `name`, `applied`) VALUES 
('dashboard', '0005_activitylog_usersession', NOW());

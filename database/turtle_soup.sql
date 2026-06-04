-- 
-- 海龜湯遊戲資料庫架構
-- 整合了所有表結構和初始數據
-- 

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- ========================================
-- 創建資料庫
-- ========================================
CREATE DATABASE IF NOT EXISTS `turtle_soup` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `turtle_soup`;

-- ========================================
-- 資料表 1: users (用戶表)
-- ========================================
CREATE TABLE IF NOT EXISTS `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ========================================
-- 資料表 2: game_stories (遊戲故事表)
-- ========================================
CREATE TABLE IF NOT EXISTS `game_stories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) DEFAULT NULL,
  `story` text DEFAULT NULL,
  `answer` text DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 插入遊戲故事數據
INSERT INTO `game_stories` (`id`, `title`, `story`, `answer`) VALUES
(1, '經典海龜湯', '男子走進餐廳點了一碗海龜湯，喝了一口就自殺了。', '他曾遇難，隊友做湯給他喝說是海龜肉。直到今天喝到真的海龜湯，才明白當年吃的是親生兒子的肉。'),
(2, '水草', '男子和女友去游泳，女友腳抽筋溺水。男子潛水沒救到人，幾年後重遊舊地看見老人在釣魚，老人說這裡從沒長過水草，男子隨即跳河自殺。', '當年他潛水救人時抓到一把「水草」，如今得知沒水草，才明白那是女友的頭髮，是他親手把女友推向深淵。'),
(3, '火車', '一名男子搭火車到鄰近的城鎮去看病，當天是最後的療程，男子已經痊癒。當他滿心歡喜地搭上火車要回家時，男子卻在途中跳車自殺，請問是為什麼？', '男子原先是位盲人，治好眼疾以後重見光明，原本滿心歡喜的他，在火車進入全黑的隧道時，讓他以為他又再次失去了光明，因此在絕望之下自殺身亡。');

-- ========================================
-- 資料表 3: submissions (投稿表)
-- ========================================
CREATE TABLE IF NOT EXISTS `submissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `story` text DEFAULT NULL,
  `answer` text DEFAULT NULL,
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 插入投稿數據
INSERT INTO `submissions` (`id`, `user_id`, `title`, `story`, `answer`) VALUES
(1, NULL, '火車', '一名男子搭火車到鄰近的城鎮去看病，當天是最後的療程，男子已經痊癒。當他滿心歡喜地搭上火車要回家時，男子卻在途中跳車自殺，請問是為什麼？', '男子原先是位盲人，治好眼疾以後重見光明，原本滿心歡喜的他，在火車進入全黑的隧道時，讓他以為他又再次失去了光明，因此在絕望之下自殺身亡。');

-- ========================================
-- 自動遞增設置
-- ========================================
ALTER TABLE `users` AUTO_INCREMENT=1;
ALTER TABLE `game_stories` AUTO_INCREMENT=4;
ALTER TABLE `submissions` AUTO_INCREMENT=2;

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;

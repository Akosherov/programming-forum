-- Database export of 'Forum Schema'

CREATE DATABASE IF NOT EXISTS `forum_schema2.0`;

USE `forum_schema2.0`;

SET NAMES utf8;

DROP TABLE IF EXISTS `replies`;
CREATE TABLE `replies` (
  `reply_id` int(11) NOT NULL AUTO_INCREMENT,
  `topic_id` int(11) NOT NULL,
  `author_id` int(11) NOT NULL,
  `reply_content` varchar(8192) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `is_best` tinyint(4) NOT NULL DEFAULT 0,
  PRIMARY KEY (`reply_id`),
  KEY `fk_replies_topics1_idx` (`topic_id`),
  KEY `fk_replies_users1_idx` (`author_id`),
  CONSTRAINT `fk_replies_topics1` FOREIGN KEY (`topic_id`) REFERENCES `topics` (`topic_id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `fk_replies_users1` FOREIGN KEY (`author_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `replies` (`reply_id`, `topic_id`, `author_id`, `reply_content`, `created_at`, `is_best`) VALUES (1, 5, 12, 'Variables and data types are one of the first concepts every programmer should master. It’s especially important to understand the difference between mutable and immutable types, as this affects how data can be modified in memory. For example, strings are immutable in Python, which means creating a modified version actually creates a new object. This can impact performance and behavior in larger applications.', '2026-03-01 17:30:46', 0);
INSERT INTO `replies` (`reply_id`, `topic_id`, `author_id`, `reply_content`, `created_at`, `is_best`) VALUES (2, 3, 12, 'Great introduction! One of the most important concepts to master early is how JavaScript interacts with the DOM, since it allows you to dynamically update content, handle user input, and create responsive interfaces. Understanding asynchronous programming with fetch, async/await, and Promises is also essential when working with APIs. Once these fundamentals are clear, transitioning to frameworks like React becomes much easier because they build on the same core principles. I’d also recommend using browser developer tools to debug and inspect elements while learning.', '2026-03-01 20:10:07', 0);
INSERT INTO `replies` (`reply_id`, `topic_id`, `author_id`, `reply_content`, `created_at`, `is_best`) VALUES (4, 3, 21, 'This is a solid starting point! I’d add that practicing with small projects—like a to-do list, a simple calculator, or a weather app—really helps cement the concepts. Also, getting comfortable with JavaScript’s event loop and understanding how callbacks, Promises, and async/await work together will make handling asynchronous operations much smoother. Lastly, don’t underestimate the value of learning about ES6 modules and how to organize your code—it pays off when scaling up to larger projects or using frameworks like React or Vue.', '2026-03-01 22:21:38', 0);

DROP TABLE IF EXISTS `reply_reactions`;
CREATE TABLE `reply_reactions` (
  `user_id` int(11) NOT NULL,
  `reply_id` int(11) NOT NULL,
  `is_like` tinyint(4) NOT NULL,
  PRIMARY KEY (`user_id`,`reply_id`),
  KEY `fk_users_has_replies_replies1_idx` (`reply_id`),
  KEY `fk_users_has_replies_users1_idx` (`user_id`),
  CONSTRAINT `fk_users_has_replies_replies1` FOREIGN KEY (`reply_id`) REFERENCES `replies` (`reply_id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `fk_users_has_replies_users1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `reply_reactions` (`user_id`, `reply_id`, `is_like`) VALUES (12, 4, 1);
INSERT INTO `reply_reactions` (`user_id`, `reply_id`, `is_like`) VALUES (21, 2, 1);

DROP TABLE IF EXISTS `topic_invitations`;
CREATE TABLE `topic_invitations` (
  `invitation_id` int(11) NOT NULL AUTO_INCREMENT,
  `topic_id` int(11) NOT NULL,
  `invited_user_id` int(11) NOT NULL,
  `invited_by_id` int(11) NOT NULL,
  `invitation_status` tinyint(4) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`invitation_id`),
  UNIQUE KEY `uq_topic_invited_user` (`topic_id`,`invited_user_id`),
  KEY `fk_topic_invitations_topics1_idx` (`topic_id`),
  KEY `fk_topic_invitations_users1_idx` (`invited_user_id`),
  KEY `fk_topic_invitations_users2_idx` (`invited_by_id`),
  CONSTRAINT `fk_topic_invitations_topics1` FOREIGN KEY (`topic_id`) REFERENCES `topics` (`topic_id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `fk_topic_invitations_users1` FOREIGN KEY (`invited_user_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_topic_invitations_users2` FOREIGN KEY (`invited_by_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `topic_invitations` (`invitation_id`, `topic_id`, `invited_user_id`, `invited_by_id`, `invitation_status`, `created_at`) VALUES (1, 6, 12, 21, 1, '2026-03-01 22:38:23');

DROP TABLE IF EXISTS `topic_participants`;
CREATE TABLE `topic_participants` (
  `topic_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`topic_id`,`user_id`),
  KEY `fk_topics_has_users_users1_idx` (`user_id`),
  KEY `fk_topics_has_users_topics1_idx` (`topic_id`),
  CONSTRAINT `fk_topics_has_users_topics1` FOREIGN KEY (`topic_id`) REFERENCES `topics` (`topic_id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `fk_topics_has_users_users1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `topic_participants` (`topic_id`, `user_id`) VALUES (4, 1);
INSERT INTO `topic_participants` (`topic_id`, `user_id`) VALUES (6, 12);
INSERT INTO `topic_participants` (`topic_id`, `user_id`) VALUES (6, 21);

DROP TABLE IF EXISTS `topics`;
CREATE TABLE `topics` (
  `topic_id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(128) NOT NULL,
  `content` varchar(8192) NOT NULL,
  `is_locked` tinyint(4) NOT NULL DEFAULT 0,
  `is_private` tinyint(4) NOT NULL DEFAULT 0,
  `reply_count` int(11) NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `author_id` int(11) NOT NULL,
  PRIMARY KEY (`topic_id`),
  KEY `fk_topics_users1_idx` (`author_id`),
  CONSTRAINT `fk_topics_users1` FOREIGN KEY (`author_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `topics` (`topic_id`, `title`, `content`, `is_locked`, `is_private`, `reply_count`, `created_at`, `author_id`) VALUES (1, 'Basics of Python Topic', 'Python is a beginner-friendly programming language known for its simple syntax and readability. This topic covers variables, loops, functions, and core programming concepts.', 0, 0, 0, '2026-02-27 22:00:13', 1);
INSERT INTO `topics` (`topic_id`, `title`, `content`, `is_locked`, `is_private`, `reply_count`, `created_at`, `author_id`) VALUES (2, 'Understanding Object-Oriented Programming in Java', 'Object-oriented programming (OOP) in Java allows developers to create modular and reusable code. Key concepts include classes, objects, inheritance, encapsulation, and polymorphism. This topic explores these concepts with practical examples and best practices for clean, maintainable Java code.', 0, 0, 0, '2026-02-27 22:07:05', 1);
INSERT INTO `topics` (`topic_id`, `title`, `content`, `is_locked`, `is_private`, `reply_count`, `created_at`, `author_id`) VALUES (3, 'Introduction to Web Development with JavaScript', 'JavaScript is the programming language of the web, enabling interactive websites and dynamic content. We will discuss DOM manipulation, events, ES6 features, and working with APIs. By the end, you will be able to create interactive web pages and understand how front-end frameworks like React use JavaScript.', 0, 0, 0, '2026-02-27 22:07:42', 1);
INSERT INTO `topics` (`topic_id`, `title`, `content`, `is_locked`, `is_private`, `reply_count`, `created_at`, `author_id`) VALUES (4, 'Getting Started with SQL and Databases', 'Databases are essential for storing and retrieving structured data efficiently. This topic covers SQL basics, including creating tables, inserting and querying data, and understanding relationships between tables. We’ll also touch on joins, indexes, and best practices for writing efficient queries.', 0, 1, 0, '2026-02-27 22:12:43', 1);
INSERT INTO `topics` (`topic_id`, `title`, `content`, `is_locked`, `is_private`, `reply_count`, `created_at`, `author_id`) VALUES (5, 'Understanding Variables and Data Types in Programming', 'Variables are fundamental building blocks in programming used to store and manage data. Each variable has a data type, such as integer, string, or boolean, which defines what kind of value it can hold and how it can be used. Understanding variables and data types is essential for writing efficient and logical code in any programming language.', 0, 0, 0, '2026-03-01 17:29:16', 12);
INSERT INTO `topics` (`topic_id`, `title`, `content`, `is_locked`, `is_private`, `reply_count`, `created_at`, `author_id`) VALUES (6, 'Understanding REST API Design and Best Practices.', 'REST APIs are the backbone of modern web applications, allowing different systems to communicate with each other in a standardized way. In this private discussion, we can explore core REST principles such as resource-based URLs, proper use of HTTP methods (GET, POST, PUT, DELETE), status codes, and authentication using JWT tokens. We can also discuss best practices for structuring endpoints, handling errors consistently, and designing scalable backend services. This topic is especially useful for developers building backend systems with frameworks like FastAPI, Django, or Express.', 0, 1, 0, '2026-03-01 20:50:09', 21);

DROP TABLE IF EXISTS `user_roles`;
CREATE TABLE `user_roles` (
  `role_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_role` varchar(32) NOT NULL,
  PRIMARY KEY (`role_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `user_roles` (`role_id`, `user_role`) VALUES (1, 'Admin');
INSERT INTO `user_roles` (`role_id`, `user_role`) VALUES (2, 'User');

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT,
  `first_name` varchar(32) NOT NULL,
  `last_name` varchar(32) NOT NULL,
  `email` varchar(256) NOT NULL,
  `username` varchar(16) NOT NULL,
  `password` varchar(256) NOT NULL,
  `is_blocked` tinyint(4) NOT NULL DEFAULT 0,
  `is_deleted` tinyint(4) NOT NULL DEFAULT 0,
  `role_id` int(11) NOT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `email_UNIQUE` (`email`),
  UNIQUE KEY `username_UNIQUE` (`username`),
  KEY `fk_users_user_roles1_idx` (`role_id`),
  CONSTRAINT `fk_users_user_roles1` FOREIGN KEY (`role_id`) REFERENCES `user_roles` (`role_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (1, 'John', 'Doe', 'jdoe@example.com', 'jdoe', '$2b$12$ika3vOaCiqIJLvQOKFQD0.pmHtnj/NVJ9KoWOrd9gyuXVKAyC0Y4m', 0, 0, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (2, 'Jane', 'Doe', 'doej@example.com', 'doej', '$2b$12$Jb6qYm0KUYKV2/YeKQ5gf.a0ftb17hLCD6DyAMx7DKHjNXZp6CI9S', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (3, 'John', 'Smith', 'jsmith@example.com', 'jsmith', '$2b$12$D8S1MMYWIeqGMZ1pcfKCBO2lZ9yuQHvwdjIfDa8d2S1qd6RPj4lpq', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (4, 'Alice', 'Johnson', 'ajohnson@example.com', 'ajohnson', '$2b$12$RiUM5RUpeaZFUrcG.2lcdeqOXi0DrVqJ41VqsWy23FSZtzhWbskh.', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (5, 'Bob', 'Williams', 'bwilliams@example.com', 'bwilliams', '$2b$12$kQPx7Kh2J2IY/eVISZMRv.FvQSVM475sK/M7vQD7DShBazAlKweCC', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (6, 'Carol', 'Brown', 'cbrown@example.com', 'cbrown', '$2b$12$d5VzCcruuwL8Z1gFkCMu.eF/aAyOoXo6BCngMycPCpxDzFvoutN7u', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (7, 'David', 'Davis', 'ddavis@example.com', 'ddavis', '$2b$12$9UbxxrTNQAr5omBlH.E8luWattA7YrROkG6UuJ.rh14JafMK0FNF.', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (8, 'Eve', 'Miller', 'emiller@example.com', 'emiller', '$2b$12$MoC/xtkmdIZkW4qQ0/YZYuaoZnx9rftgEDV/wFDzGPn0q67XpkgD.', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (9, 'Frank', 'Wilson', 'fwilson@example.com', 'fwilson', '$2b$12$CuE4TJ4px.cVhN9MmxvCte20DQXfg/PaKasC1mWk9zsIG48twqPMS', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (10, 'Grace', 'Moore', 'gmoore@example.com', 'gmoore', '$2b$12$d3niuqm45cF503Jaj6NwDebi8JBm0IIHAWHkVPxc6kyQrwR7AkDdu', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (11, 'Henry', 'Taylor', 'htaylor@example.com', 'htaylor', '$2b$12$AJmunPsDlYjfC0gWqbw5nOnD95J.fL61XnaF6BGI8pWGfsMJuu8Fa', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (12, 'Pesho', 'Peshev', 'ppeshev@example.com', 'ppeshev', '$2b$12$Ye.arSJMzVcJUOnXmIZbR.2jrb/tYuZsUTLMBLM2lrw5cplL6.mp2', 0, 0, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (13, 'Emily', 'Johnson', 'ejohnson@example.com', 'ejohnson', 'pass123', 0, 1, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (14, 'Michael', 'Brown', 'mbrown@example.com', 'mbrown', 'pass123', 1, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (15, 'Sarah', 'Davis', 'sdavis@example.com', 'sdavis', 'pass123', 0, 1, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (16, 'David', 'Wilson', 'dwilson@example.com', 'dwilson', 'pass123', 0, 1, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (17, 'Anna', 'Taylor', 'ataylor@example.com', 'ataylor', 'pass123', 0, 1, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (18, 'Daniel', 'Anderson', 'danderson@example.com', 'danderson', 'pass123', 1, 0, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (19, 'Laura', 'Thomas', 'lthomas@example.com', 'lthomas', 'pass123', 0, 0, 1);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (20, 'Ivan', 'Ivanov', 'iivanov@example.com', 'Ivanov', '$2b$12$fAesgkkUfAsug8qtlvT6B.o0qiP7JkUHmH8png5LPWLJILzy0P.ii', 0, 0, 2);
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `username`, `password`, `is_blocked`, `is_deleted`, `role_id`) VALUES (21, 'Petar', 'Petroff', 'ppetrov@example.com', 'ppetrov', '$2b$12$cPOuy5h721TFlJLyTeo4wu4ZEc.ZVh6oykBCkPw62VM3B6Swgjx4y', 0, 0, 2);


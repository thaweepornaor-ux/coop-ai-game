CREATE TABLE `answers` (
	`room_code` text NOT NULL,
	`round_id` integer NOT NULL,
	`question_index` integer NOT NULL,
	`player_id` text NOT NULL,
	`choice` integer NOT NULL,
	`answered_at` integer NOT NULL,
	PRIMARY KEY(`room_code`, `round_id`, `question_index`, `player_id`),
	FOREIGN KEY (`room_code`) REFERENCES `rooms`(`code`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`room_code`,`player_id`) REFERENCES `players`(`room_code`,`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `players` (
	`id` text PRIMARY KEY NOT NULL,
	`room_code` text NOT NULL,
	`token_hash` text NOT NULL,
	`name` text NOT NULL,
	`avatar_json` text DEFAULT '{}' NOT NULL,
	`created_at` integer NOT NULL,
	FOREIGN KEY (`room_code`) REFERENCES `rooms`(`code`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `players_token_hash_unique` ON `players` (`token_hash`);--> statement-breakpoint
CREATE UNIQUE INDEX `players_room_id_unique` ON `players` (`room_code`,`id`);--> statement-breakpoint
CREATE INDEX `players_room_created_idx` ON `players` (`room_code`,`created_at`);--> statement-breakpoint
CREATE TABLE `rate_limits` (
	`key` text PRIMARY KEY NOT NULL,
	`count` integer NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `rooms` (
	`code` text PRIMARY KEY NOT NULL,
	`host_token_hash` text NOT NULL,
	`phase` text DEFAULT 'lobby' NOT NULL,
	`question_index` integer DEFAULT -1 NOT NULL,
	`round_id` integer DEFAULT 1 NOT NULL,
	`deadline` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);

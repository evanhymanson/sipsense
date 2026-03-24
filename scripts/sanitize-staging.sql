-- scripts/sanitize-staging.sql
--
-- Anonymizes PII in the staging database after importing production data.
-- Run ONLY against sipsense_staging, NEVER against sipsense (production).

-- Safety check: abort if connected to the wrong database
DO $$
BEGIN
    IF current_database() <> 'sipsense_staging' THEN
        RAISE EXCEPTION 'REFUSING TO RUN: connected to "%" instead of sipsense_staging',
            current_database();
    END IF;
END $$;

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- 1. Build username mapping: real_username -> user_NNN
-- ═══════════════════════════════════════════════════════════════════════

CREATE TEMP TABLE _username_map AS
SELECT
    username AS old_username,
    'user_' || LPAD(ROW_NUMBER() OVER (ORDER BY id)::text, 4, '0') AS new_username
FROM users;

-- ═══════════════════════════════════════════════════════════════════════
-- 2. Anonymize the users table
-- ═══════════════════════════════════════════════════════════════════════
-- All staging users get password: staging_test_password
-- Hash generated with: python3 -c "import bcrypt; print(bcrypt.hashpw(b'staging_test_password', bcrypt.gensalt()).decode())"

UPDATE users SET
    username        = m.new_username,
    email           = m.new_username || '@staging.sipsense.test',
    hashed_password = '$2b$12$OX2xdYDTYpFGDogdj8.Wu.BdjnQMGlhYDJX/fcsH68FWWjHs8ruIK'
FROM _username_map m
WHERE users.username = m.old_username;

-- ═══════════════════════════════════════════════════════════════════════
-- 3. Remap user_id/username across all referencing tables
--    (user_id columns store the username string, not an integer FK)
-- ═══════════════════════════════════════════════════════════════════════

UPDATE user_ratings SET user_id = m.new_username
FROM _username_map m WHERE user_ratings.user_id = m.old_username;

UPDATE user_favorites SET user_id = m.new_username
FROM _username_map m WHERE user_favorites.user_id = m.old_username;

UPDATE user_memory SET user_id = m.new_username
FROM _username_map m WHERE user_memory.user_id = m.old_username;

UPDATE collection_items SET user_id = m.new_username
FROM _username_map m WHERE collection_items.user_id = m.old_username;

UPDATE toasts SET user_id = m.new_username
FROM _username_map m WHERE toasts.user_id = m.old_username;

UPDATE user_badges SET user_id = m.new_username
FROM _username_map m WHERE user_badges.user_id = m.old_username;

UPDATE user_journey_progress SET user_id = m.new_username
FROM _username_map m WHERE user_journey_progress.user_id = m.old_username;

-- follows: both columns are usernames
UPDATE follows SET follower_id = m.new_username
FROM _username_map m WHERE follows.follower_id = m.old_username;
UPDATE follows SET following_id = m.new_username
FROM _username_map m WHERE follows.following_id = m.old_username;

-- watchlist tables use "username" column
UPDATE watchlist_items SET username = m.new_username
FROM _username_map m WHERE watchlist_items.username = m.old_username;

UPDATE watchlist_alerts SET username = m.new_username
FROM _username_map m WHERE watchlist_alerts.username = m.old_username;
UPDATE watchlist_alerts SET from_username = m.new_username
FROM _username_map m WHERE watchlist_alerts.from_username = m.old_username;

UPDATE videos SET user_id = m.new_username
FROM _username_map m WHERE videos.user_id = m.old_username;

UPDATE video_toasts SET user_id = m.new_username
FROM _username_map m WHERE video_toasts.user_id = m.old_username;

UPDATE video_comments SET user_id = m.new_username
FROM _username_map m WHERE video_comments.user_id = m.old_username;

UPDATE store_availability SET user_id = m.new_username
FROM _username_map m WHERE store_availability.user_id = m.old_username;

UPDATE affiliate_clicks SET user_id = m.new_username
FROM _username_map m WHERE affiliate_clicks.user_id = m.old_username;

UPDATE user_subscriptions SET user_id = m.new_username
FROM _username_map m WHERE user_subscriptions.user_id = m.old_username;

-- ═══════════════════════════════════════════════════════════════════════
-- 4. Scrub free-text PII fields (keep structure, replace content)
-- ═══════════════════════════════════════════════════════════════════════

UPDATE user_memory SET preferences = '{}';

UPDATE user_ratings SET
    notes = CASE WHEN notes IS NOT NULL THEN 'Sample tasting note for staging.' ELSE NULL END,
    location_note = CASE WHEN location_note IS NOT NULL THEN 'Staging Location' ELSE NULL END;

UPDATE collection_items SET
    personal_notes = CASE WHEN personal_notes IS NOT NULL THEN 'Staging collection note.' ELSE NULL END,
    purchase_location = CASE WHEN purchase_location IS NOT NULL THEN 'Staging Store' ELSE NULL END;

UPDATE video_comments SET text = 'Sample staging comment #' || id::text;

UPDATE videos SET location_name = CASE WHEN location_name IS NOT NULL THEN 'Staging Location' ELSE NULL END;

UPDATE watchlist_alerts SET message = 'Staging alert notification';

-- Clear external payment provider IDs
UPDATE user_subscriptions SET external_id = NULL;

-- ═══════════════════════════════════════════════════════════════════════
-- 5. Truncate analytics/tracking tables (not needed for feature testing)
-- ═══════════════════════════════════════════════════════════════════════

TRUNCATE TABLE analytics_events;
TRUNCATE TABLE user_actions;

-- ═══════════════════════════════════════════════════════════════════════
-- 6. Clear AI cache (may contain user-specific responses)
-- ═══════════════════════════════════════════════════════════════════════

TRUNCATE TABLE ai_cache;

-- ═══════════════════════════════════════════════════════════════════════
-- 7. Clean up
-- ═══════════════════════════════════════════════════════════════════════

DROP TABLE _username_map;

COMMIT;

-- Verify
SELECT 'Sanitization complete. User count: ' || count(*) || ', sample user: ' || min(username)
FROM users;

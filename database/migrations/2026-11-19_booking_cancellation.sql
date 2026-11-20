-- =====================================================================
-- Migrare: motivul și autorul anulării unei rezervări.
-- Pentru o bază de date EXISTENTĂ, fără să pierzi datele
-- (alternativa: rulezi din nou schema.sql + seed.sql, care șterge totul).
-- Rulează în pgAdmin 4 -> Query Tool pe baza `db_campus_sports`.
-- Poate fi rulată de mai multe ori fără erori.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cancellation_source') THEN
        CREATE TYPE cancellation_source AS ENUM
            ('user', 'administrator', 'maintenance', 'university_activity', 'system');
    END IF;
END $$;

ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancelled_by  cancellation_source;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancel_reason varchar(300);

-- Rezervările deja anulate nu au motiv; le marcăm ca anulate de utilizator.
UPDATE bookings SET cancelled_by = 'user'
WHERE status = 'cancelled' AND cancelled_by IS NULL;

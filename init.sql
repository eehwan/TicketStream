CREATE DATABASE event_db;
CREATE DATABASE reservation_db;
CREATE DATABASE order_db;




-- Connect to event_db to insert test event and seats
\c event_db;

-- Create events table if not exists
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,
    total_seats INTEGER NOT NULL,
    available_seats INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create seats table if not exists
CREATE TABLE IF NOT EXISTS seats (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    seat_number VARCHAR(50) NOT NULL,
    is_reserved BOOLEAN DEFAULT FALSE,
    UNIQUE(event_id, seat_number)
);

-- Insert test event
INSERT INTO events (name, description, event_date, total_seats, available_seats) VALUES ('Concert A', 'A great concert', '2025-07-20 19:00:00+00', 50, 50) ON CONFLICT (id) DO NOTHING;

-- Insert 50 test seats for Event ID 1
DO $$
BEGIN
    FOR i IN 1..50 LOOP
        INSERT INTO seats (event_id, seat_number, is_reserved) VALUES (1, 'A' || i::text, FALSE) ON CONFLICT (event_id, seat_number) DO NOTHING;
    END LOOP;
END $$;

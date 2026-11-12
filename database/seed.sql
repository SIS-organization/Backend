-- =====================================================================
-- Date de test. Rulează DUPĂ schema.sql, în același Query Tool.
-- Parolele sunt valori de umplutură: autentificarea reală vine în Epic 3.
-- =====================================================================

INSERT INTO users (email, first_name, last_name, password_hash, role) VALUES
    ('andrei.munteanu@student.usv.ro', 'Andrei',        'Munteanu', '!seed-fara-login', 'student'),
    ('daria.stan@student.usv.ro',      'Daria',         'Stan',     '!seed-fara-login', 'student'),
    ('elena.rusu@usv.ro',              'Elena',         'Rusu',     '!seed-fara-login', 'professor'),
    ('admin@usv.ro',                   'Administrator', 'Baza Sportiva', '!seed-fara-login', 'administrator'),
    ('vlad.ciobanu@example.com',       'Vlad',          'Ciobanu',  '!seed-fara-login', 'external');

INSERT INTO facilities (name, type, capacity, location) VALUES
    ('Teren',         'football_field', 1, 'Campus USV'),
    ('Sală fitness',  'gym',            1, 'Campus USV'),
    ('Bazin',         'swimming_pool',  4, 'Campus USV'),   -- 4 culoare = 4 rezervări simultane
    ('Sală de sport', 'sports_hall',    1, 'Campus USV');

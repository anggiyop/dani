
-- ============================================
-- Schema: Asisten Mahasiswa (PostgreSQL 14+)
-- Timezone assumption: Asia/Jakarta (set at app level)
-- ID strategy: UUID v4 (generated in app or DB via gen_random_uuid())
-- ============================================

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========== ENUMS ==========
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'day_name') THEN
        CREATE TYPE day_name AS ENUM ('Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'exam_type') THEN
        CREATE TYPE exam_type AS ENUM ('UTS','UAS');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_category') THEN
        CREATE TYPE event_category AS ENUM ('sempro','semhas','sidang','kalender');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticket_status') THEN
        CREATE TYPE ticket_status AS ENUM ('submitted','in_review','need_revision','approved','rejected','completed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('student','staff','admin');
    END IF;
END $$;

-- ========== MASTER AKADEMIK ==========
CREATE TABLE IF NOT EXISTS students (
    npm            VARCHAR(20) PRIMARY KEY,
    name           VARCHAR(120) NOT NULL,
    email          VARCHAR(120) UNIQUE,
    fakultas       VARCHAR(120),
    prodi          VARCHAR(120),
    angkatan       INTEGER,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lecturers (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nidn           VARCHAR(20),
    name           VARCHAR(120) NOT NULL,
    email          VARCHAR(120),
    fakultas       VARCHAR(120),
    prodi          VARCHAR(120),
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS courses (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code           VARCHAR(20) UNIQUE NOT NULL,
    name           VARCHAR(160) NOT NULL,
    sks            SMALLINT NOT NULL CHECK (sks BETWEEN 1 AND 10),
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS classes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id      UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lecturer_id    UUID REFERENCES lecturers(id) ON DELETE SET NULL,
    term_code      VARCHAR(20) NOT NULL, -- mis. 2025Ganjil
    year           INTEGER NOT NULL,
    day            day_name NOT NULL,
    start_time     TIME NOT NULL,
    end_time       TIME NOT NULL,
    room           VARCHAR(60),
    quota          INTEGER,
    notes          TEXT,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now(),
    CHECK (end_time > start_time)
);
CREATE INDEX IF NOT EXISTS idx_classes_term ON classes(term_code, day, start_time);
CREATE INDEX IF NOT EXISTS idx_classes_lecturer ON classes(lecturer_id);

CREATE TABLE IF NOT EXISTS enrollments (
    student_npm    VARCHAR(20) REFERENCES students(npm) ON DELETE CASCADE,
    class_id       UUID REFERENCES classes(id) ON DELETE CASCADE,
    PRIMARY KEY (student_npm, class_id),
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exams (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id      UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    class_id       UUID REFERENCES classes(id) ON DELETE SET NULL,
    type           exam_type NOT NULL,
    date           DATE NOT NULL,
    start_time     TIME NOT NULL,
    end_time       TIME NOT NULL,
    room           VARCHAR(60),
    term_code      VARCHAR(20) NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now(),
    CHECK (end_time > start_time)
);
CREATE INDEX IF NOT EXISTS idx_exams_term ON exams(term_code, date);

CREATE TABLE IF NOT EXISTS events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category       event_category NOT NULL,
    title          VARCHAR(200) NOT NULL,
    date           DATE NOT NULL,
    start_time     TIME,
    end_time       TIME,
    location       VARCHAR(160),
    organizer      VARCHAR(160),
    description    TEXT,
    related_npm    VARCHAR(20), -- untuk sempro/sidang jika spesifik ke mahasiswa
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

-- ========== LAYANAN (SOP-ULT) ==========
CREATE TABLE IF NOT EXISTS services (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(160) NOT NULL, -- contoh: Cetak Bukti SPP
    description    TEXT,
    unit_owner     VARCHAR(160), -- ULT/BKK/LPSE/TIK
    sla_days       INTEGER,      -- SLA dari SOP
    fee_rp         INTEGER,      -- 0 jika gratis
    is_active      BOOLEAN DEFAULT TRUE,
    sop_ref        TEXT,         -- nomor/halaman/tautan internal
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_requirements (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id     UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    item           VARCHAR(200) NOT NULL,
    is_mandatory   BOOLEAN DEFAULT TRUE,
    note           TEXT,
    sort_no        SMALLINT DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_requirements_service ON service_requirements(service_id);

CREATE TABLE IF NOT EXISTS service_workflows (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id     UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    step_no        SMALLINT NOT NULL,
    description    TEXT NOT NULL,
    link_url       TEXT
);
CREATE INDEX IF NOT EXISTS idx_workflows_service ON service_workflows(service_id);

CREATE TABLE IF NOT EXISTS service_documents (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id     UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    product_name   VARCHAR(160) NOT NULL -- contoh: KTMS, Surat Keterangan KIP
);

-- ========== TIKET LAYANAN ==========
CREATE TABLE IF NOT EXISTS tickets (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_npm    VARCHAR(20) NOT NULL REFERENCES students(npm) ON DELETE CASCADE,
    service_id     UUID NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    status         ticket_status NOT NULL DEFAULT 'submitted',
    attachments    JSONB, -- simpan metadata file (nama, url, tipe)
    note           TEXT,
    due_date       DATE,  -- bisa di-set = created_at::date + sla_days
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tickets_student ON tickets(student_npm);
CREATE INDEX IF NOT EXISTS idx_tickets_service ON tickets(service_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

CREATE TABLE IF NOT EXISTS ticket_logs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id      UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    actor          VARCHAR(120) NOT NULL, -- npm/email/role
    action         VARCHAR(80) NOT NULL,  -- status change / comment / upload
    message        TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ticket_logs_ticket ON ticket_logs(ticket_id);

-- ========== AUTH (sederhana) ==========
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role           user_role NOT NULL,
    email          VARCHAR(120) UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    student_npm    VARCHAR(20) REFERENCES students(npm) ON DELETE SET NULL,
    staff_unit     VARCHAR(120),
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

-- ========== TRIGGER UPDATE TIMESTAMP ==========
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ DECLARE
    t RECORD;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE format('
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name=''%s'' AND column_name=''updated_at'') THEN
          DROP TRIGGER IF EXISTS trg_%s_updated ON %I;
          CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
        END IF;
      END $$;
    ', t.tablename, t.tablename, t.tablename, t.tablename, t.tablename);
  END LOOP;
END $$;

-- ========== SAMPLE SERVICES SEED (opsional) ==========
INSERT INTO services (id, name, description, unit_owner, sla_days, fee_rp, sop_ref)
VALUES
    (gen_random_uuid(),'Cetak Bukti SPP','Pencetakan bukti SPP terakhir','ULT',1,0,'SOP ULT 2023'),
    (gen_random_uuid(),'KTM Hilang','Pengajuan KTM baru melalui LPSE','LPSE',5,0,'SOP ULT 2023'),
    (gen_random_uuid(),'KTMS (Sementara)','Penerbitan Kartu Tanda Mahasiswa Sementara','ULT',1,0,'SOP ULT 2023')
ON CONFLICT DO NOTHING;

-- IDB Loan Application System - Database Schema & Seed Data

-- ========================================
-- TABLES
-- ========================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('borrower', 'officer', 'risk', 'admin')),
    full_name VARCHAR(128) NOT NULL,
    country VARCHAR(64),
    department VARCHAR(128),
    employee_id VARCHAR(32) UNIQUE,
    phone VARCHAR(32),
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    notes TEXT,
    preferences JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- App-number sequence — used by /api/applications POST to avoid the
-- count(*)+1 race condition. Starts at 100 so seed rows keep their nice
-- IDB-2024-00xx numbers.
CREATE SEQUENCE IF NOT EXISTS loan_app_no_seq START 100;

CREATE TABLE loan_applications (
    id SERIAL PRIMARY KEY,
    app_no VARCHAR(32) UNIQUE NOT NULL,
    borrower_id INTEGER REFERENCES users(id),
    project_name VARCHAR(256) NOT NULL,
    project_description TEXT,
    sector VARCHAR(64),
    amount_requested NUMERIC(18, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    term_months INTEGER,
    interest_rate NUMERIC(6, 4),
    purpose TEXT,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN (
        'draft', 'submitted', 'under_review', 'pending_supplement',
        'risk_assessment', 'approved', 'rejected', 'disbursed', 'archived'
    )),
    officer_id INTEGER REFERENCES users(id),
    risk_analyst_id INTEGER REFERENCES users(id),
    rejection_reason TEXT,
    submitted_at TIMESTAMP,
    reviewed_at TIMESTAMP,
    approved_at TIMESTAMP,
    disbursed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE supplements (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(id) ON DELETE CASCADE,
    requested_by INTEGER REFERENCES users(id),
    description TEXT,
    response TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'responded', 'closed')),
    requested_at TIMESTAMP DEFAULT NOW(),
    responded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(id) ON DELETE CASCADE,
    supplement_id INTEGER REFERENCES supplements(id) ON DELETE SET NULL,
    uploaded_by INTEGER REFERENCES users(id),
    filename VARCHAR(256) NOT NULL,
    original_name VARCHAR(256) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_type VARCHAR(128),
    file_size INTEGER,
    file_hash VARCHAR(128),
    category VARCHAR(128),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE review_comments (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    comment TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 10),
    checklist JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    username VARCHAR(64),
    action VARCHAR(128),
    resource_type VARCHAR(64),
    resource_id INTEGER,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE system_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(128) UNIQUE NOT NULL,
    value TEXT,
    description TEXT,
    updated_by INTEGER REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(256),
    message TEXT,
    type VARCHAR(32) DEFAULT 'info',
    is_read BOOLEAN DEFAULT false,
    related_type VARCHAR(64),
    related_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE backup_snapshots (
    id SERIAL PRIMARY KEY,
    imported_by INTEGER REFERENCES users(id),
    original_filename VARCHAR(256),
    payload_bytes BYTEA,
    payload_kind VARCHAR(64),
    imported_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    key_prefix VARCHAR(16),
    key_hash VARCHAR(128),
    scopes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP
);

-- ========================================
-- INDEXES
-- ========================================

CREATE INDEX idx_applications_borrower ON loan_applications(borrower_id);
CREATE INDEX idx_applications_status ON loan_applications(status);
CREATE INDEX idx_applications_officer ON loan_applications(officer_id);
CREATE INDEX idx_documents_application ON documents(application_id);
CREATE INDEX idx_supplements_application ON supplements(application_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);

-- ========================================
-- SEED DATA — Users
-- ========================================

-- Borrower accounts (country representatives)
INSERT INTO users (username, email, password_hash, role, full_name, country, department, employee_id) VALUES
('br_cn_liwei',     'liwei@member-gov.cn',     'scrypt:32768:8:1$salt$hash_placeholder_01', 'borrower', 'Li Wei',         'China',        'Ministry of Finance',       'CN-FIN-0042'),
('br_br_silva',     'silva@member-gov.br',     'scrypt:32768:8:1$salt$hash_placeholder_02', 'borrower', 'Carlos Silva',   'Brazil',       'Ministry of Economy',       'BR-ECO-0019'),
('br_in_sharma',    'sharma@member-gov.in',    'scrypt:32768:8:1$salt$hash_placeholder_03', 'borrower', 'Priya Sharma',   'India',        'Dept of Economic Affairs',   'IN-DEA-0234'),
('br_za_nkosi',     'nkosi@member-gov.za',     'scrypt:32768:8:1$salt$hash_placeholder_04', 'borrower', 'Thabo Nkosi',    'South Africa', 'National Treasury',         'ZA-TRS-0078'),
('br_ru_petrov',    'petrov@member-gov.ru',    'scrypt:32768:8:1$salt$hash_placeholder_05', 'borrower', 'Alexei Petrov',  'Russia',       'Ministry of Finance',       'RU-FIN-0156'),
('br_ae_almansoori','almansoori@member-gov.ae','scrypt:32768:8:1$salt$hash_placeholder_06', 'borrower', 'Fatima AlMansoori','UAE',       'Ministry of Finance',       'AE-FIN-0031'),
('br_eg_elmasry',   'elmasry@member-gov.eg',   'scrypt:32768:8:1$salt$hash_placeholder_07', 'borrower', 'Ahmed ElMasry',  'Egypt',        'Ministry of Planning',      'EG-PLN-0112'),
('br_bd_rahman',    'rahman@member-gov.bd',    'scrypt:32768:8:1$salt$hash_placeholder_08', 'borrower', 'Farah Rahman',   'Bangladesh',   'ERD Ministry',              'BD-ERD-0045');

-- Officer accounts (IDB project officers - internal)
INSERT INTO users (username, email, password_hash, role, full_name, country, department, employee_id) VALUES
('of_anderson',     'j.anderson@idb.int',      'scrypt:32768:8:1$salt$hash_placeholder_09', 'officer', 'James Anderson', NULL,       'Infrastructure Dept',       'EMP-10042'),
('of_nguyen',       't.nguyen@idb.int',        'scrypt:32768:8:1$salt$hash_placeholder_10', 'officer', 'Thao Nguyen',     NULL,       'Energy & Transport',        'EMP-10078'),
('of_patel',        'a.patel@idb.int',         'scrypt:32768:8:1$salt$hash_placeholder_11', 'officer', 'Anjali Patel',    NULL,       'Water & Sanitation',        'EMP-10103'),
('of_kim',          'h.kim@idb.int',           'scrypt:32768:8:1$salt$hash_placeholder_12', 'officer', 'Hyun-woo Kim',    NULL,       'Digital Infrastructure',    'EMP-10129');

-- Risk Analyst accounts (IDB internal)
INSERT INTO users (username, email, password_hash, role, full_name, country, department, employee_id) VALUES
('ri_mueller',      'k.mueller@idb.int',       'scrypt:32768:8:1$salt$hash_placeholder_13', 'risk',    'Klaus Mueller',   NULL,       'Risk Management',           'EMP-20015'),
('ri_oconnor',      'm.oconnor@idb.int',       'scrypt:32768:8:1$salt$hash_placeholder_14', 'risk',    'Maeve O''Connor',  NULL,      'Credit Risk',               'EMP-20042');

-- Admin accounts (IDB IT/Security)
INSERT INTO users (username, email, password_hash, role, full_name, country, department, employee_id) VALUES
('ad_martinez',     'c.martinez@idb.int',      'scrypt:32768:8:1$salt$hash_placeholder_15', 'admin',   'Carlos Martinez', NULL,       'IT Operations',             'EMP-90001'),
('ad_tanaka',       'y.tanaka@idb.int',        'scrypt:32768:8:1$salt$hash_placeholder_16', 'admin',   'Yuki Tanaka',     NULL,       'Information Security',      'EMP-90015');

-- ========================================
-- SEED DATA — Loan Applications
-- ========================================

INSERT INTO loan_applications (app_no, borrower_id, project_name, project_description, sector, amount_requested, currency, term_months, interest_rate, purpose, status, officer_id, risk_analyst_id, submitted_at, reviewed_at, approved_at, disbursed_at)
VALUES
-- China projects
('IDB-2024-0012', 1, 'Yangtze River Basin Ecological Restoration Phase II',
 'Comprehensive watershed management including reforestation of 12,000 hectares, wetland restoration in the middle reaches, and installation of water quality monitoring stations across 47 sites.',
 'Environment', 480000000.00, 'USD', 240, 2.15,
 'Environmental sustainability and climate resilience in the Yangtze River Basin',
 'disbursed', 9, 13, '2024-01-15', '2024-02-20', '2024-03-10', '2024-04-01'),

('IDB-2024-0028', 1, 'Rural Healthcare Digitization Program',
 'Deployment of telemedicine infrastructure across 500 rural clinics, electronic health records system integration, and training of 2,000 healthcare workers in digital diagnostics.',
 'Healthcare', 320000000.00, 'USD', 180, 2.30,
 'Digital transformation of rural healthcare delivery',
 'approved', 10, 14, '2024-02-01', '2024-03-05', '2024-03-28', NULL),

-- Brazil projects
('IDB-2024-0041', 2, 'Amazon Renewable Energy Grid Project',
 'Construction of 3 solar farms (total capacity 450MW) and 2 wind farms (280MW) with transmission lines connecting remote Amazon communities to the national grid.',
 'Energy', 550000000.00, 'USD', 300, 2.50,
 'Renewable energy access for underserved Amazon region',
 'risk_assessment', 9, 14, '2024-02-20', '2024-03-15', NULL, NULL),

('IDB-2024-0047', 2, 'Sao Paulo Metro Line 7 Extension',
 'Extension of metro line 7 by 18km with 12 new stations, including smart ticketing system and accessibility features.',
 'Transport', 720000000.00, 'USD', 360, 2.75,
 'Urban mobility improvement for Sao Paulo metropolitan area',
 'under_review', 10, NULL, '2024-03-01', NULL, NULL, NULL),

-- India projects
('IDB-2024-0055', 3, 'National Smart Grid Modernization',
 'Upgrade of power distribution infrastructure across 8 states with smart meters, automated substations, and demand-response management systems.',
 'Energy', 410000000.00, 'USD', 240, 2.35,
 'Modernization of India''s electricity distribution network',
 'submitted', NULL, NULL, '2024-03-10', NULL, NULL, NULL),

('IDB-2024-0062', 3, 'Mumbai Coastal Resilience Infrastructure',
 'Construction of sea walls, storm surge barriers, drainage system upgrades, and mangrove restoration across 45km of Mumbai coastline.',
 'Infrastructure', 290000000.00, 'USD', 300, 2.20,
 'Climate adaptation and coastal protection for Mumbai',
 'draft', NULL, NULL, NULL, NULL, NULL, NULL),

-- South Africa projects
('IDB-2024-0071', 4, 'Johannesburg Water Supply Augmentation',
 'Lesotho Highlands water transfer Phase 3, new treatment plant (capacity 400ML/day), and replacement of 120km aging pipeline network.',
 'Water', 380000000.00, 'USD', 240, 2.40,
 'Water security for Gauteng province',
 'pending_supplement', 11, NULL, '2024-03-20', '2024-04-05', NULL, NULL),

-- UAE project
('IDB-2024-0079', 6, 'Abu Dhabi Sustainable City Expansion',
 'Development of Masdar City Phase 2 with net-zero buildings, autonomous electric transit network, and integrated waste-to-energy facility.',
 'Urban Development', 630000000.00, 'USD', 300, 2.65,
 'Sustainable urban development model for arid climates',
 'under_review', 12, NULL, '2024-04-01', NULL, NULL, NULL),

-- Egypt project
('IDB-2024-0083', 7, 'Nile Delta Agricultural Modernization',
 'Installation of drip irrigation systems across 50,000 hectares, solar-powered pumps, cold chain logistics hubs, and farmer cooperative digitization.',
 'Agriculture', 185000000.00, 'USD', 180, 2.10,
 'Agricultural productivity and water efficiency in the Nile Delta',
 'submitted', NULL, NULL, '2024-04-05', NULL, NULL, NULL),

-- Russia project
('IDB-2024-0001', 5, 'Far East Port & Logistics Hub Development',
 'Construction of deep-water container terminal (capacity 2M TEU/year), rail intermodal yard, and digital customs clearance platform in Vladivostok.',
 'Transport', 890000000.00, 'USD', 420, 3.10,
 'Strategic trade corridor connecting Asia-Pacific to Eurasian rail networks',
 'draft', NULL, NULL, NULL, NULL, NULL, NULL);

-- ========================================
-- SEED DATA — Supplements & Documents (samples)
-- ========================================

INSERT INTO supplements (application_id, requested_by, description, status, requested_at, responded_at)
VALUES
(7, 11, 'Please provide detailed environmental impact assessment for the Lesotho water transfer component. The current documentation lacks hydrological modeling data.', 'pending', '2024-04-05', NULL),
(3, 14, 'We need updated grid interconnection studies for the Amazon solar farms. Please include load flow analysis for peak demand scenarios.', 'responded', '2024-03-18', '2024-04-02');

INSERT INTO documents (application_id, uploaded_by, filename, original_name, file_path, file_type, file_size, category)
VALUES
(1, 1, 'yangtze_feasibility_v2.pdf', 'Yangtze_Basin_Feasibility_v2.pdf', '/app/uploads/1/yangtze_feasibility_v2.pdf', 'application/pdf', 4820000, 'feasibility_study'),
(1, 1, 'yangtze_budget_fy24.xlsx', 'FY2024_Budget_Breakdown.xlsx', '/app/uploads/1/yangtze_budget_fy24.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 1520000, 'financial'),
(3, 2, 'amazon_eia_summary.pdf', 'Amazon_RE_EIA_Summary.pdf', '/app/uploads/3/amazon_eia_summary.pdf', 'application/pdf', 3200000, 'environmental'),
(5, 3, 'smart_grid_tech_spec.pdf', 'SmartGrid_Technical_Specs.pdf', '/app/uploads/5/smart_grid_tech_spec.pdf', 'application/pdf', 5800000, 'technical');

-- ========================================
-- SEED DATA — Review Comments
-- ========================================

INSERT INTO review_comments (application_id, user_id, comment, rating)
VALUES
(1, 9,  'Project aligns well with IDB''s environmental mandate. Feasibility study is comprehensive. Recommend approval with standard monitoring conditions.', 8),
(1, 13, 'Financial projections appear conservative. Debt service coverage ratio calculated at 2.1x — within acceptable range for sovereign borrowers.', 7),
(2, 10, 'Telemedicine initiative is timely. However, recommend phased rollout starting with 100 clinics to validate the digital infrastructure before scaling.', 7),
(3, 9,  'Solar/wind hybrid design is technically sound. Grid integration study needs peer review before final assessment.', 6);

-- ========================================
-- SEED DATA — System Config
-- ========================================

INSERT INTO system_config (key, value, description) VALUES
('min_loan_amount', '10000000', 'Minimum loan amount in USD'),
('max_loan_amount', '2000000000', 'Maximum loan amount in USD'),
('default_interest_spread', '0.75', 'Default spread over reference rate (%)'),
('max_term_months', '480', 'Maximum loan term in months'),
('auto_archive_days', '1825', 'Days after disbursement to auto-archive'),
('allowed_currencies', 'USD,EUR,CNY,BRL,INR,ZAR,AED,RUB', 'Approved loan currencies'),
('upload_max_size_mb', '50', 'Maximum file upload size in MB'),
('allowed_file_types', 'pdf,doc,docx,xls,xlsx,ppt,pptx,csv,jpg,png', 'Allowed upload extensions'),
('enable_interest_rate_override', 'true', 'Allow risk analysts to manually override calculated rates'),
('sso_enabled', 'true', 'Enable SSO authentication for member government users');
-- NOTE: sso_enabled=true but callback URL validation is missing — VULN-02

-- ============================================================
-- LawPro Converter - Supabase Database Schema
-- ============================================================
-- 이 SQL을 Supabase 대시보드 > SQL Editor에서 실행하세요

-- 1. Users 테이블 (회원)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100),
    password_hash VARCHAR(255),  -- 비밀번호 해시 (또는 OAuth 사용)

    -- 크레딧 시스템
    credits INTEGER DEFAULT 0,           -- 남은 크레딧
    total_credits_used INTEGER DEFAULT 0, -- 총 사용 크레딧

    -- 상태
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,

    -- 메타데이터
    memo TEXT,                            -- 관리자 메모
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);


-- 2. Conversions 테이블 (변환 기록)
CREATE TABLE IF NOT EXISTS conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- 파일 정보
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,      -- 'hwpx', 'docx', 'xlsx', 'pptx', 'pdf', 'image_pdf'
    file_size BIGINT,                    -- 바이트
    page_count INTEGER DEFAULT 1,

    -- 크레딧
    credits_used INTEGER DEFAULT 0,

    -- 상태
    status VARCHAR(50) DEFAULT 'completed',  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,

    -- 시간
    processing_time_ms INTEGER,          -- 처리 시간 (밀리초)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_conversions_user_id ON conversions(user_id);
CREATE INDEX IF NOT EXISTS idx_conversions_file_type ON conversions(file_type);
CREATE INDEX IF NOT EXISTS idx_conversions_created_at ON conversions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversions_status ON conversions(status);


-- 3. Error Patterns 테이블 (학습된 오류 패턴)
CREATE TABLE IF NOT EXISTS error_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 패턴 정보
    original VARCHAR(500) NOT NULL,      -- 오류 텍스트
    corrected VARCHAR(500) NOT NULL,     -- 정답 텍스트
    source VARCHAR(50) NOT NULL,         -- 'image_pdf' 또는 'digital_doc'

    -- 분류
    category VARCHAR(100) DEFAULT 'unknown',  -- 오류 카테고리
    context TEXT,                        -- 문맥 정보
    reason TEXT,                         -- 수정 이유

    -- 통계 (사용빈도 추적)
    frequency INTEGER DEFAULT 1,         -- 사용자 제출 횟수
    usage_count INTEGER DEFAULT 0,       -- AI 검수에서 실제 사용된 횟수

    -- 상태
    is_active BOOLEAN DEFAULT TRUE,      -- 활성화 여부

    -- 시간
    last_used TIMESTAMPTZ,               -- 마지막 사용 시간
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 (효과성 점수 기준 정렬용)
CREATE INDEX IF NOT EXISTS idx_patterns_source ON error_patterns(source);
CREATE INDEX IF NOT EXISTS idx_patterns_usage ON error_patterns(usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_patterns_frequency ON error_patterns(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_patterns_is_active ON error_patterns(is_active);
CREATE INDEX IF NOT EXISTS idx_patterns_original ON error_patterns(original);
CREATE INDEX IF NOT EXISTS idx_patterns_effectiveness ON error_patterns(usage_count DESC, frequency DESC);

-- 중복 방지 (같은 출처의 동일 패턴)
CREATE UNIQUE INDEX IF NOT EXISTS idx_patterns_unique
    ON error_patterns(original, corrected, source);


-- 4. Correction Logs 테이블 (수정 내역 로그)
CREATE TABLE IF NOT EXISTS correction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- 파일 정보
    file_name VARCHAR(500),
    file_type VARCHAR(50),

    -- 수정 정보
    original VARCHAR(1000) NOT NULL,     -- 원본 텍스트
    corrected VARCHAR(1000) NOT NULL,    -- 수정된 텍스트
    context TEXT,                        -- 주변 문맥
    category VARCHAR(100),               -- 오류 카테고리
    reason TEXT,                         -- 수정 이유

    -- 결정
    decision VARCHAR(50) NOT NULL,       -- 'confirmed', 'rejected', 'modified'

    -- 시간
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_corrections_user_id ON correction_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_corrections_decision ON correction_logs(decision);
CREATE INDEX IF NOT EXISTS idx_corrections_file_type ON correction_logs(file_type);
CREATE INDEX IF NOT EXISTS idx_corrections_created_at ON correction_logs(created_at DESC);


-- 5. Config 테이블 (설정)
CREATE TABLE IF NOT EXISTS config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 기본 설정 삽입
INSERT INTO config (key, value) VALUES
('pattern_limits', '{
    "max_patterns": 5000,
    "max_patterns_per_source": 2500,
    "min_usage_to_keep": 0,
    "cleanup_threshold": 6000,
    "prompt_pattern_limit": 100,
    "target_llm": "gpt-4o"
}'::jsonb)
ON CONFLICT (key) DO NOTHING;


-- 6. App Stats 테이블 (앱 통계)
CREATE TABLE IF NOT EXISTS app_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stat_date DATE UNIQUE NOT NULL,

    -- 일별 통계
    downloads INTEGER DEFAULT 0,
    installs INTEGER DEFAULT 0,
    signups INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    pages_converted INTEGER DEFAULT 0,
    credits_used INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_app_stats_date ON app_stats(stat_date DESC);


-- ============================================================
-- 함수 및 트리거
-- ============================================================

-- updated_at 자동 갱신 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 각 테이블에 트리거 적용
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_error_patterns_updated_at
    BEFORE UPDATE ON error_patterns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_config_updated_at
    BEFORE UPDATE ON config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- Row Level Security (RLS)
-- ============================================================
-- Supabase에서는 기본적으로 RLS가 활성화됩니다.
-- service_role 키를 사용하면 RLS를 우회할 수 있습니다.

-- RLS 활성화
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversions ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE config ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_stats ENABLE ROW LEVEL SECURITY;

-- 서비스 역할 정책 (관리자 API용)
-- service_role 키를 사용하면 모든 작업 가능
CREATE POLICY "Service role full access" ON users
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON conversions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON error_patterns
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON correction_logs
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON config
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON app_stats
    FOR ALL USING (auth.role() = 'service_role');

-- 공개 읽기 정책 (패턴 조회용)
CREATE POLICY "Public read active patterns" ON error_patterns
    FOR SELECT USING (is_active = true);


-- ============================================================
-- 뷰 (통계용)
-- ============================================================

-- 일별 변환 통계 뷰
CREATE OR REPLACE VIEW daily_conversion_stats AS
SELECT
    DATE(created_at) as stat_date,
    COUNT(*) as total_conversions,
    SUM(page_count) as total_pages,
    SUM(credits_used) as total_credits,
    COUNT(DISTINCT user_id) as unique_users,
    file_type,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'failed') as failed
FROM conversions
GROUP BY DATE(created_at), file_type
ORDER BY stat_date DESC;

-- 패턴 효과성 순위 뷰
CREATE OR REPLACE VIEW pattern_effectiveness_ranking AS
SELECT
    id,
    original,
    corrected,
    source,
    category,
    frequency,
    usage_count,
    (usage_count * 2 + frequency) as effectiveness_score,
    is_active,
    last_used,
    created_at
FROM error_patterns
WHERE is_active = true
ORDER BY effectiveness_score DESC;


-- ============================================================
-- 샘플 데이터 (테스트용, 프로덕션에서는 제거)
-- ============================================================

-- 관리자 계정 (프로덕션에서는 별도로 생성)
-- INSERT INTO users (email, name, is_admin, is_active)
-- VALUES ('admin@lawpro.kr', '관리자', true, true);

-- 샘플 오류 패턴
INSERT INTO error_patterns (original, corrected, source, category, reason) VALUES
('계약Z', '계약을', 'image_pdf', 'ocr_한영혼동', 'OCR이 을을 Z로 인식'),
('권리Z', '권리를', 'image_pdf', 'ocr_한영혼동', 'OCR이 를을 Z로 인식'),
('것E', '것은', 'image_pdf', 'ocr_한영혼동', 'OCR이 은을 E로 인식'),
('게1조', '제1조', 'image_pdf', 'ocr_법률용어', 'OCR이 제를 게로 인식'),
('게2항', '제2항', 'image_pdf', 'ocr_법률용어', 'OCR이 제를 게로 인식'),
('벌률', '법률', 'image_pdf', 'ocr_오타', 'OCR이 법을 벌로 인식')
ON CONFLICT DO NOTHING;


-- 완료!
SELECT 'Database schema created successfully!' as result;

-- =====================================================
-- StudyZen Enhanced Schema - Migration
-- Adds features: Tasks, Notes, Focus Timer, Exams, Streaks
-- Keeps existing: Groups, Channels, Messages
-- =====================================================

USE studyzen;

-- =====================================================
-- 1. SUBJECTS TABLE (Group-level)
-- =====================================================
CREATE TABLE IF NOT EXISTS subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    subject_name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7) DEFAULT '#4CAF50',
    icon VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    INDEX idx_group_id (group_id)
);

-- =====================================================
-- 2. GROUP TASKS/ASSIGNMENTS
-- =====================================================
CREATE TABLE IF NOT EXISTS group_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    subject_id INT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    assigned_by INT NOT NULL,
    assigned_to INT, -- NULL for group-wide task
    priority ENUM('low', 'medium', 'high') DEFAULT 'medium',
    due_date DATE,
    due_time TIME,
    status ENUM('pending', 'in_progress', 'completed') DEFAULT 'pending',
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_group_id (group_id),
    INDEX idx_status (status),
    INDEX idx_due_date (due_date)
);

-- =====================================================
-- 3. STUDY SESSIONS (Focus Timer)
-- =====================================================
CREATE TABLE IF NOT EXISTS study_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT,
    subject_id INT,
    task_id INT,
    session_type ENUM('focus', 'short_break', 'long_break') DEFAULT 'focus',
    duration_minutes INT NOT NULL,
    planned_duration_minutes INT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NOT NULL,
    completed BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE SET NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY (task_id) REFERENCES group_tasks(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_date (DATE(started_at))
);

-- =====================================================
-- 4. GROUP NOTES/SHARED NOTES
-- =====================================================
CREATE TABLE IF NOT EXISTS group_notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    subject_id INT,
    channel_id INT,
    created_by INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content LONGTEXT NOT NULL,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_group_id (group_id),
    INDEX idx_subject_id (subject_id)
);

-- =====================================================
-- 5. EXAMS/ASSIGNMENTS TRACKER
-- =====================================================
CREATE TABLE IF NOT EXISTS exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    subject_id INT,
    title VARCHAR(255) NOT NULL,
    exam_type ENUM('exam', 'quiz', 'assignment') DEFAULT 'exam',
    exam_date DATE NOT NULL,
    exam_time TIME,
    location VARCHAR(255),
    description TEXT,
    created_by INT NOT NULL,
    status ENUM('upcoming', 'completed') DEFAULT 'upcoming',
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_group_id (group_id),
    INDEX idx_exam_date (exam_date)
);

-- =====================================================
-- 6. STUDY STREAKS (Group and Personal)
-- =====================================================
CREATE TABLE IF NOT EXISTS study_streaks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT,
    current_streak INT DEFAULT 0,
    max_streak INT DEFAULT 0,
    last_study_date DATE,
    streak_frozen_until TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_group_streak (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
);

-- =====================================================
-- 7. DAILY STATISTICS (For performance & analytics)
-- =====================================================
CREATE TABLE IF NOT EXISTS daily_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT,
    date DATE NOT NULL,
    total_study_time INT DEFAULT 0,
    tasks_completed INT DEFAULT 0,
    tasks_pending INT DEFAULT 0,
    study_streak INT DEFAULT 0,
    had_study_session BOOLEAN DEFAULT FALSE,
    UNIQUE KEY unique_stat (user_id, group_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    INDEX idx_user_date (user_id, date)
);

-- =====================================================
-- 8. NOTIFICATIONS
-- =====================================================
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT,
    notification_type ENUM('task_assigned', 'task_completed', 'exam_reminder', 'new_note', 'streak_milestone', 'general') DEFAULT 'general',
    title VARCHAR(255) NOT NULL,
    message TEXT,
    related_id INT,
    is_read BOOLEAN DEFAULT FALSE,
    action_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_is_read (is_read),
    INDEX idx_created_at (created_at)
);

-- =====================================================
-- 9. USER SETTINGS/PREFERENCES
-- =====================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    theme VARCHAR(20) DEFAULT 'light',
    notifications_enabled BOOLEAN DEFAULT TRUE,
    email_notifications_enabled BOOLEAN DEFAULT TRUE,
    study_goal_minutes INT DEFAULT 120,
    pomodoro_duration INT DEFAULT 25,
    break_duration INT DEFAULT 5,
    long_break_duration INT DEFAULT 15,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- 10. MEMBER CONTRIBUTIONS (Track who did what)
-- =====================================================
CREATE TABLE IF NOT EXISTS member_contributions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT NOT NULL,
    contribution_type ENUM('task_completed', 'note_created', 'message_sent', 'study_session') DEFAULT 'task_completed',
    points INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
    INDEX idx_user_group (user_id, group_id)
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_group_tasks_group ON group_tasks(group_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user ON study_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_group_notes_group ON group_notes(group_id);
CREATE INDEX IF NOT EXISTS idx_exams_group ON exams(group_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);

-- =====================================================
-- Add new columns to existing users table for enhanced profile
-- =====================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS study_goal INT DEFAULT 120;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_study_time INT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP;

-- =====================================================
-- Sample Data (Optional - for development)
-- =====================================================

-- Insert subjects for Software Development group
INSERT IGNORE INTO subjects (group_id, subject_name, description, color, icon) VALUES
(1, 'Frontend Development', 'HTML, CSS, JavaScript, React', '#2196F3', '💻'),
(1, 'Backend Development', 'Node.js, Python, Databases', '#FF9800', '⚙️'),
(1, 'Mobile Development', 'React Native, Flutter', '#9C27B0', '📱');

-- Insert sample tasks
INSERT IGNORE INTO group_tasks (group_id, subject_id, title, description, assigned_by, priority, due_date, status) VALUES
(1, 1, 'Build a Todo App with React', 'Create a functional Todo application with add, edit, delete features', 1, 'high', DATE_ADD(CURDATE(), INTERVAL 7 DAY), 'pending'),
(1, 2, 'Set up Database Schema', 'Design and implement MySQL database for our project', 1, 'high', DATE_ADD(CURDATE(), INTERVAL 5 DAY), 'in_progress');

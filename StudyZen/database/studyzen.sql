-- Note: run this AFTER the "studyzen" database already exists.
-- Postgres doesn't support CREATE DATABASE IF NOT EXISTS or USE inside a script.
 
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    profile_picture TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
 
CREATE TABLE IF NOT EXISTS study_groups (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    member_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
 
CREATE TABLE IF NOT EXISTS group_members (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT NOT NULL,
    role VARCHAR(20) DEFAULT 'member' CHECK (role IN ('admin', 'moderator', 'member')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
);
 
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    group_id INT NOT NULL,
    channel_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (group_id, channel_name),
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
);
 
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
 
INSERT INTO study_groups (group_name, description, category, member_count) VALUES
('Software Development', 'Build projects, review code, and learn programming together.', '💻', 120),
('Mathematics', 'Sharpen equations, problem solving and concepts with supportive peers.', '📚', 95),
('Science', 'Explore biology, physics and chemistry with shared experiments and notes.', '🔬', 88),
('Geography', 'Discuss interesting places, maps, cultures and global topics.', '🌎', 72),
('English', 'Improve writing, reading and speaking through group discussions.', '📖', 64),
('Creative Studies', 'Share ideas, art inspiration and creative project feedback.', '🎨', 58);
 
INSERT INTO channels (group_id, channel_name, description) VALUES
(1, 'general', 'General discussion for software development'),
(1, 'projects', 'Share and review programming projects'),
(1, 'resources', 'Useful tutorials, documentation and tools'),
(2, 'general', 'Math homework and concept discussions'),
(2, 'problems', 'Problem solving and exercises'),
(3, 'general', 'Science discussions and experiments'),
(3, 'research', 'Share research papers and findings')
ON CONFLICT (group_id, channel_name) DO NOTHING;
 

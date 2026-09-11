-- Migration: Add Discord-like features to StudyZen
-- This adds channels and messages support

-- Alter group_members table to add role
ALTER TABLE group_members ADD COLUMN role ENUM('admin', 'moderator', 'member') DEFAULT 'member' AFTER group_id;

-- Create channels table
CREATE TABLE IF NOT EXISTS channels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    channel_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Insert default channels for existing groups
INSERT INTO channels (group_id, channel_name, description) VALUES
(1, 'general', 'General discussion for software development'),
(1, 'projects', 'Share and review programming projects'),
(1, 'resources', 'Useful tutorials, documentation and tools'),
(2, 'general', 'Math homework and concept discussions'),
(2, 'problems', 'Problem solving and exercises'),
(3, 'general', 'Science discussions and experiments'),
(3, 'research', 'Share research papers and findings'),
(4, 'general', 'Geography discussions and map sharing'),
(5, 'general', 'English literature and writing discussions'),
(5, 'writing', 'Share your writing and get feedback'),
(6, 'general', 'Creative ideas and inspiration sharing'),
(6, 'artwork', 'Share and critique artwork and designs')
ON DUPLICATE KEY UPDATE channel_name=channel_name;

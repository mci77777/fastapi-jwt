-- E2E数据库断言查询脚本
-- 用于验证匿名用户会话和消息数据的一致性

-- ============================================================================
-- 用户侧断言
-- ============================================================================

-- 断言1: 检查匿名用户记录
-- 验证users表中存在匿名用户，且isanonymous=true，lastloginat已更新
SELECT 
    'users_anonymous_check' as assertion_name,
    COUNT(*) as anonymous_user_count,
    COUNT(CASE WHEN isanonymous = true THEN 1 END) as anonymous_flag_count,
    COUNT(CASE WHEN lastloginat > NOW() - INTERVAL '1 hour' THEN 1 END) as recent_login_count,
    MIN(lastloginat) as earliest_login,
    MAX(lastloginat) as latest_login
FROM users 
WHERE isanonymous = true
  AND createdat > NOW() - INTERVAL '1 hour';

-- 断言2: 检查匿名用户的基本属性
SELECT 
    'users_anonymous_attributes' as assertion_name,
    id as user_id,
    email,
    isanonymous,
    createdat,
    lastloginat,
    CASE 
        WHEN email IS NULL OR email = '' THEN 'valid_anonymous_email'
        ELSE 'unexpected_email'
    END as email_status,
    CASE 
        WHEN isanonymous = true THEN 'correct_anonymous_flag'
        ELSE 'incorrect_anonymous_flag'
    END as anonymous_flag_status
FROM users 
WHERE isanonymous = true
  AND createdat > NOW() - INTERVAL '1 hour'
ORDER BY createdat DESC
LIMIT 10;

-- ============================================================================
-- 会话与消息侧断言
-- ============================================================================

-- 断言3: 检查匿名用户的会话记录
-- 验证chat_sessions表中存在关联user_id的会话，message_count >= 1
SELECT 
    'chat_sessions_anonymous' as assertion_name,
    cs.id as session_id,
    cs.user_id,
    cs.message_count,
    cs.createdat as session_created,
    cs.updatedat as session_updated,
    u.isanonymous,
    CASE 
        WHEN cs.message_count >= 1 THEN 'has_messages'
        ELSE 'no_messages'
    END as message_status,
    CASE 
        WHEN cs.updatedat > cs.createdat THEN 'session_updated'
        ELSE 'session_not_updated'
    END as update_status
FROM chat_sessions cs
JOIN users u ON cs.user_id = u.id
WHERE u.isanonymous = true
  AND cs.createdat > NOW() - INTERVAL '1 hour'
ORDER BY cs.createdat DESC;

-- 断言4: 检查匿名用户的消息记录
-- 验证chat_raw表中存在role='user'和对应的assistant消息
SELECT 
    'chat_raw_anonymous' as assertion_name,
    cr.id as message_id,
    cr.session_id,
    cr.role,
    cr.content,
    cr.final_markdown,
    cr.createdat as message_created,
    cs.user_id,
    u.isanonymous,
    CASE 
        WHEN cr.final_markdown IS NOT NULL AND cr.final_markdown != '' THEN 'has_final_content'
        ELSE 'no_final_content'
    END as final_content_status,
    CASE 
        WHEN cr.session_id IS NOT NULL THEN 'valid_session_link'
        ELSE 'invalid_session_link'
    END as session_link_status
FROM chat_raw cr
JOIN chat_sessions cs ON cr.session_id = cs.id
JOIN users u ON cs.user_id = u.id
WHERE u.isanonymous = true
  AND cr.createdat > NOW() - INTERVAL '1 hour'
ORDER BY cr.createdat DESC;

-- 断言5: 检查消息的配对情况（用户消息 + AI回复）
SELECT 
    'message_pairing_check' as assertion_name,
    session_id,
    COUNT(*) as total_messages,
    COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
    COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages,
    CASE 
        WHEN COUNT(CASE WHEN role = 'user' THEN 1 END) = COUNT(CASE WHEN role = 'assistant' THEN 1 END) 
        THEN 'balanced_conversation'
        ELSE 'unbalanced_conversation'
    END as pairing_status
FROM chat_raw cr
JOIN chat_sessions cs ON cr.session_id = cs.id
JOIN users u ON cs.user_id = u.id
WHERE u.isanonymous = true
  AND cr.createdat > NOW() - INTERVAL '1 hour'
GROUP BY session_id
ORDER BY session_id;

-- ============================================================================
-- 外键和约束检查
-- ============================================================================

-- 断言6: 检查外键完整性
SELECT 
    'foreign_key_integrity' as assertion_name,
    'chat_sessions_to_users' as relationship,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN u.id IS NOT NULL THEN 1 END) as valid_user_links,
    COUNT(CASE WHEN u.id IS NULL THEN 1 END) as broken_user_links
FROM chat_sessions cs
LEFT JOIN users u ON cs.user_id = u.id
WHERE cs.createdat > NOW() - INTERVAL '1 hour'

UNION ALL

SELECT 
    'foreign_key_integrity' as assertion_name,
    'chat_raw_to_sessions' as relationship,
    COUNT(*) as total_messages,
    COUNT(CASE WHEN cs.id IS NOT NULL THEN 1 END) as valid_session_links,
    COUNT(CASE WHEN cs.id IS NULL THEN 1 END) as broken_session_links
FROM chat_raw cr
LEFT JOIN chat_sessions cs ON cr.session_id = cs.id
WHERE cr.createdat > NOW() - INTERVAL '1 hour';

-- ============================================================================
-- 时间戳合理性检查
-- ============================================================================

-- 断言7: 检查时间戳的合理性
SELECT 
    'timestamp_consistency' as assertion_name,
    'users_timestamps' as table_name,
    COUNT(*) as total_records,
    COUNT(CASE WHEN createdat <= lastloginat THEN 1 END) as valid_timestamp_order,
    COUNT(CASE WHEN createdat > lastloginat THEN 1 END) as invalid_timestamp_order,
    MIN(createdat) as earliest_created,
    MAX(lastloginat) as latest_login
FROM users 
WHERE isanonymous = true
  AND createdat > NOW() - INTERVAL '1 hour'

UNION ALL

SELECT 
    'timestamp_consistency' as assertion_name,
    'chat_sessions_timestamps' as table_name,
    COUNT(*) as total_records,
    COUNT(CASE WHEN createdat <= updatedat THEN 1 END) as valid_timestamp_order,
    COUNT(CASE WHEN createdat > updatedat THEN 1 END) as invalid_timestamp_order,
    MIN(createdat) as earliest_created,
    MAX(updatedat) as latest_updated
FROM chat_sessions cs
JOIN users u ON cs.user_id = u.id
WHERE u.isanonymous = true
  AND cs.createdat > NOW() - INTERVAL '1 hour';

-- ============================================================================
-- 可选：向量/记忆相关检查（如果启用）
-- ============================================================================

-- 断言8: 检查消息嵌入状态（如果启用向量功能）
-- 注意：这个查询可能需要根据实际的表结构调整
/*
SELECT 
    'message_embedding_check' as assertion_name,
    COUNT(*) as total_messages_with_embedding,
    COUNT(CASE WHEN embedding_status = 'completed' THEN 1 END) as completed_embeddings,
    COUNT(CASE WHEN embedding_status = 'pending' THEN 1 END) as pending_embeddings,
    COUNT(CASE WHEN embedding_status = 'failed' THEN 1 END) as failed_embeddings
FROM message_embedding me
JOIN chat_raw cr ON me.message_id = cr.id
JOIN chat_sessions cs ON cr.session_id = cs.id
JOIN users u ON cs.user_id = u.id
WHERE u.isanonymous = true
  AND cr.createdat > NOW() - INTERVAL '1 hour';
*/

-- ============================================================================
-- 汇总统计
-- ============================================================================

-- 断言9: 匿名用户活动汇总
SELECT 
    'anonymous_activity_summary' as assertion_name,
    COUNT(DISTINCT u.id) as unique_anonymous_users,
    COUNT(DISTINCT cs.id) as total_sessions,
    COUNT(cr.id) as total_messages,
    AVG(cs.message_count) as avg_messages_per_session,
    MIN(u.createdat) as first_anonymous_user_created,
    MAX(cr.createdat) as last_message_created,
    EXTRACT(EPOCH FROM (MAX(cr.createdat) - MIN(u.createdat))) as activity_duration_seconds
FROM users u
LEFT JOIN chat_sessions cs ON u.id = cs.user_id
LEFT JOIN chat_raw cr ON cs.id = cr.session_id
WHERE u.isanonymous = true
  AND u.createdat > NOW() - INTERVAL '1 hour';

-- ============================================================================
-- 数据质量检查
-- ============================================================================

-- 断言10: 数据质量检查
SELECT 
    'data_quality_check' as assertion_name,
    'null_checks' as check_type,
    COUNT(CASE WHEN u.id IS NULL THEN 1 END) as null_user_ids,
    COUNT(CASE WHEN cs.user_id IS NULL THEN 1 END) as null_session_user_ids,
    COUNT(CASE WHEN cr.session_id IS NULL THEN 1 END) as null_message_session_ids,
    COUNT(CASE WHEN cr.content IS NULL OR cr.content = '' THEN 1 END) as empty_message_content
FROM users u
LEFT JOIN chat_sessions cs ON u.id = cs.user_id
LEFT JOIN chat_raw cr ON cs.id = cr.session_id
WHERE u.isanonymous = true
  AND u.createdat > NOW() - INTERVAL '1 hour';

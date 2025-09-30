-- 近24h 匿名会话 user_type 必须为 'anonymous'
select count(*) as bad_convo_user_type
from conversations
where created_at > now() - interval '24 hours'
  and (user_type is null or user_type <> 'anonymous');

-- 每个会话至少有一条 assistant 最终消息
select s.id
from chat_sessions s
left join chat_raw r on r.session_id = s.id and r.role='assistant' and r.is_final=true
where s.created_at > now() - interval '24 hours'
group by s.id
having count(r.id) = 0;

-- JWT 相关错误的统一错误体分布（用于告警基线）
select status, code, count(*)
from api_errors
where created_at > now() - interval '24 hours'
  and code in ('auth.token_expired','auth.invalid_audience','auth.invalid_issuer')
group by status, code;

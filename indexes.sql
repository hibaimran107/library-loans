-- Performance index for the "what does this member have out" endpoint.
-- Partial: only open loans are indexed, so it stays small as history grows.
-- Ordered by borrowed_at DESC so no sort step is needed.
CREATE INDEX loans_open_by_member
    ON loans(member_id, borrowed_at DESC) WHERE returned_at IS NULL;

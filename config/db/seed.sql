DO $$
DECLARE
    v_tenant_id UUID;
BEGIN
    INSERT INTO tenants (tenant_slug, display_name)
    VALUES ('acme-support', 'Acme Support')
    ON CONFLICT (tenant_slug)
    DO UPDATE SET display_name = EXCLUDED.display_name
    RETURNING id INTO v_tenant_id;

    INSERT INTO api_keys (tenant_id, api_token, description)
    VALUES (v_tenant_id, 'acme-support-key', 'Default local development token')
    ON CONFLICT (api_token)
    DO UPDATE SET description = EXCLUDED.description, last_used_at = NULL;

    INSERT INTO policies (tenant_id, policy_id, base_model, prompt_version, adapter_ref, status)
    VALUES (
        v_tenant_id,
        'support-draft-v0',
        'meta-llama/Meta-Llama-3.1-8B-Instruct',
        'prompt-graph-v0',
        'adapters/support-draft-v0',
        'shadow'
    )
    ON CONFLICT (tenant_id, policy_id)
    DO UPDATE SET
        base_model = EXCLUDED.base_model,
        prompt_version = EXCLUDED.prompt_version,
        adapter_ref = EXCLUDED.adapter_ref,
        status = EXCLUDED.status,
        updated_at = NOW();

    INSERT INTO events (tenant_id, event_type, payload, policy_id, skill)
    VALUES (
        v_tenant_id,
        'bootstrap.note',
        jsonb_build_object(
            'message', 'Seeded development tenant and sample policy.',
            'timestamp', NOW()
        ),
        'support-draft-v0',
        'support_draft_email'
    );
END $$;

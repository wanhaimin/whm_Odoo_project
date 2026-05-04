# -*- coding: utf-8 -*-
"""Factory for configured LLM model profiles."""


def build_chat_client(env, model_profile_id=None, purpose="advisor"):
    profile_model = env["diecut.llm.model.profile"].sudo()
    profile_model.ensure_builtin_profiles()
    profile = profile_model.browse(int(model_profile_id or 0)).exists() if model_profile_id else profile_model.browse()
    if not profile:
        profile = profile_model.get_default_profile("wiki_compile" if purpose == "wiki_compile" else "advisor")
    if profile and profile.active and (profile.api_key or profile.protocol == "openclaw_worker"):
        return profile.build_client(), None, profile
    return _legacy_client(env)


def advisor_options(env):
    return env["diecut.llm.model.profile"].sudo().advisor_options()


def _legacy_client(env):
    icp = env["ir.config_parameter"].sudo()
    backend = (icp.get_param("diecut_knowledge.ai_backend") or "dify").strip()
    if backend == "claude":
        api_key = (icp.get_param("diecut_knowledge.claude_api_key") or "").strip()
        if not api_key:
            return None, "未配置 Claude API Key，请在设置中填写。", None
        model = (icp.get_param("diecut_knowledge.claude_model") or "").strip()
        base_url = (icp.get_param("diecut_knowledge.claude_base_url") or "").strip()
        max_tokens_str = (icp.get_param("diecut_knowledge.claude_max_tokens") or "").strip()
        from .claude_client import ClaudeClient

        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url
        if max_tokens_str and max_tokens_str.isdigit():
            kwargs["max_tokens"] = int(max_tokens_str)
        return ClaudeClient(**kwargs), None, None

    base_url = (icp.get_param("diecut_knowledge.dify_chat_app_url") or icp.get_param("diecut_knowledge.dify_base_url") or "").strip()
    api_key = (icp.get_param("diecut_knowledge.dify_chat_api_key") or "").strip()
    if not base_url or not api_key:
        return None, "未配置 Dify Base URL 和 Chat API Key，请在设置中填写。", None
    from .dify_client import DifyClient

    return DifyClient(base_url=base_url, api_key=api_key), None, None

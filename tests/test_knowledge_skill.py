from skills.knowledge_skill import KnowledgeSkill


def test_knowledge_skill_indexes_searches_and_reads(tmp_path):
    source = tmp_path / "project.md"
    source.write_text(
        "Project Phoenix uses Python.\nOwner notes are local.\n",
        encoding="utf-8",
    )
    skill = KnowledgeSkill(tmp_path / "knowledge.db")

    indexed = skill.index_knowledge_path(str(source))
    searched = skill.search_knowledge("Phoenix Python")
    read = skill.read_knowledge_source(
        searched["results"][0]["source_path"],
        start_line=1,
        end_line=2,
    )

    assert indexed["success"] is True
    assert searched["success"] is True
    assert searched["results"][0]["source_ref"].endswith("#L1-L2")
    assert "Project Phoenix" in read["content"]


def test_knowledge_skill_tools_mark_new_root_as_approval_gated(tmp_path):
    skill = KnowledgeSkill(tmp_path / "knowledge.db")
    tools = {tool["name"]: tool for tool in skill.get_tools()}

    assert tools["index_knowledge_path"]["needs_approval"] is True
    assert tools["refresh_knowledge_index"]["needs_approval"] is False
    assert tools["remove_knowledge_root"]["needs_approval"] is True


def test_knowledge_skill_unknown_tool_fails_cleanly(tmp_path):
    skill = KnowledgeSkill(tmp_path / "knowledge.db")
    result = skill.execute("does_not_exist", {})
    assert result["success"] is False

from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeSource
from onyx.db.enums import TaxonomyNodeStatus
from onyx.taxonomy.models import TaxonomyNodeCreate


def _default_keywords(name: str, definition: str) -> list[str]:
    return [name, *[part for part in definition.replace("、", "，").split("，") if part]]


def _leaf(
    node_id: str,
    name: str,
    definition: str,
    keywords: list[str],
    synonyms: list[str] | None = None,
) -> TaxonomyNodeCreate:
    return TaxonomyNodeCreate(
        id=node_id,
        level=TaxonomyNodeLevel.LEAF,
        name=name,
        definition=definition,
        applicability="Documents whose main intent matches this leaf category.",
        positive_examples=[f"{name} related policy, guide, report, template, or record"],
        negative_examples=["Documents whose primary topic belongs to a different leaf"],
        keywords=keywords,
        synonyms=synonyms or [],
        source=TaxonomyNodeSource.SYSTEM_DEFAULT,
        status=TaxonomyNodeStatus.DRAFT,
    )


def _l2(
    node_id: str,
    name: str,
    definition: str,
    children: list[TaxonomyNodeCreate],
) -> TaxonomyNodeCreate:
    return TaxonomyNodeCreate(
        id=node_id,
        level=TaxonomyNodeLevel.L2,
        name=name,
        definition=definition,
        applicability="Topic grouping used for navigation and leaf expansion.",
        positive_examples=[],
        negative_examples=[],
        keywords=_default_keywords(name, definition),
        synonyms=[],
        source=TaxonomyNodeSource.SYSTEM_DEFAULT,
        status=TaxonomyNodeStatus.DRAFT,
        children=children,
    )


def _l1(
    node_id: str,
    name: str,
    definition: str,
    children: list[TaxonomyNodeCreate],
) -> TaxonomyNodeCreate:
    return TaxonomyNodeCreate(
        id=node_id,
        level=TaxonomyNodeLevel.L1,
        name=name,
        definition=definition,
        applicability="Top-level enterprise knowledge domain.",
        positive_examples=[],
        negative_examples=[],
        keywords=_default_keywords(name, definition),
        synonyms=[],
        source=TaxonomyNodeSource.SYSTEM_DEFAULT,
        status=TaxonomyNodeStatus.DRAFT,
        children=children,
    )


def get_default_taxonomy_template() -> list[TaxonomyNodeCreate]:
    return [
        _l1(
            "default.company_governance",
            "公司治理与合规",
            "公司治理、制度、合规、风险控制与审计相关文档。",
            [
                _l2(
                    "default.company_governance.policies",
                    "政策与制度",
                    "企业治理制度、管理办法和合规政策。",
                    [
                        _leaf(
                            "default.company_governance.policies.charter",
                            "公司章程",
                            "公司章程、治理架构和股东会/董事会规则。",
                            ["章程", "董事会", "股东会", "治理"],
                        ),
                        _leaf(
                            "default.company_governance.policies.management",
                            "管理制度",
                            "跨部门管理制度、流程规范和授权规则。",
                            ["制度", "流程", "授权", "管理办法"],
                        ),
                        _leaf(
                            "default.company_governance.policies.compliance",
                            "合规政策",
                            "监管合规、商业道德、反舞弊和合规操作要求。",
                            ["合规", "监管", "反舞弊", "道德"],
                        ),
                    ],
                ),
                _l2(
                    "default.company_governance.risk",
                    "风险与内控",
                    "风险管理、内控流程和审计整改。",
                    [
                        _leaf(
                            "default.company_governance.risk.internal_control",
                            "内控流程",
                            "内部控制流程、风险点和控制措施。",
                            ["内控", "控制点", "风险", "整改"],
                        ),
                        _leaf(
                            "default.company_governance.risk.audit_report",
                            "审计报告",
                            "内部或外部审计报告、发现和整改记录。",
                            ["审计", "报告", "整改", "发现"],
                        ),
                    ],
                ),
            ],
        ),
        _l1(
            "default.hr",
            "人力资源文档",
            "员工、组织、招聘、薪酬福利和 HR 政策相关文档。",
            [
                _l2(
                    "default.hr.policy",
                    "HR 政策",
                    "员工行为、假期、考勤和办公安排政策。",
                    [
                        _leaf(
                            "default.hr.policy.handbook",
                            "员工手册",
                            "员工手册、行为准则和入职基本规则。",
                            ["员工手册", "行为准则", "入职", "员工规则"],
                        ),
                        _leaf(
                            "default.hr.policy.leave",
                            "假期政策",
                            "年假、病假、事假、育儿假等休假政策。",
                            ["假期", "年假", "病假", "休假", "请假"],
                            ["休假制度", "leave policy"],
                        ),
                        _leaf(
                            "default.hr.policy.attendance",
                            "考勤制度",
                            "考勤、加班、打卡、迟到早退和远程办公记录规则。",
                            ["考勤", "加班", "打卡", "迟到", "远程办公"],
                        ),
                    ],
                ),
                _l2(
                    "default.hr.lifecycle",
                    "招聘与离职",
                    "招聘、入职、转岗、绩效和离职流程。",
                    [
                        _leaf(
                            "default.hr.lifecycle.recruiting",
                            "招聘流程",
                            "岗位招聘、面试、录用和候选人管理。",
                            ["招聘", "面试", "录用", "候选人"],
                        ),
                        _leaf(
                            "default.hr.lifecycle.offboarding",
                            "离职流程",
                            "离职申请、交接、证明和资产归还。",
                            ["离职", "交接", "证明", "资产归还"],
                        ),
                    ],
                ),
            ],
        ),
        _l1(
            "default.finance_legal",
            "财务、法务与合同",
            "财务会计、预算、采购合同和法律事务相关文档。",
            [
                _l2(
                    "default.finance_legal.finance",
                    "财务与会计",
                    "财务制度、报表、预算和费用管理。",
                    [
                        _leaf(
                            "default.finance_legal.finance.expense",
                            "费用报销",
                            "差旅、报销、发票和费用审批规则。",
                            ["报销", "发票", "差旅", "费用"],
                        ),
                        _leaf(
                            "default.finance_legal.finance.budget",
                            "预算与报表",
                            "预算编制、财务报表、经营分析和月结材料。",
                            ["预算", "报表", "月结", "经营分析"],
                        ),
                    ],
                ),
                _l2(
                    "default.finance_legal.legal",
                    "法务与合同",
                    "合同模板、法律审查和争议处理文档。",
                    [
                        _leaf(
                            "default.finance_legal.legal.contract",
                            "合同模板",
                            "采购、销售、服务、保密等合同模板和条款。",
                            ["合同", "条款", "模板", "NDA", "保密协议"],
                        ),
                        _leaf(
                            "default.finance_legal.legal.dispute",
                            "争议与诉讼",
                            "争议处理、仲裁、诉讼和法律意见。",
                            ["争议", "诉讼", "仲裁", "法律意见"],
                        ),
                    ],
                ),
            ],
        ),
        _l1(
            "default.technology",
            "技术与研发",
            "技术规范、研发项目、产品文档和知识产权相关材料。",
            [
                _l2(
                    "default.technology.standards",
                    "技术规范",
                    "架构、接口、开发、测试和发布规范。",
                    [
                        _leaf(
                            "default.technology.standards.architecture",
                            "架构规范",
                            "系统架构、接口标准、技术选型和设计原则。",
                            ["架构", "接口", "技术选型", "设计原则"],
                        ),
                        _leaf(
                            "default.technology.standards.testing",
                            "测试与发布",
                            "测试策略、用例、发布流程和质量门禁。",
                            ["测试", "用例", "发布", "质量门禁"],
                        ),
                    ],
                ),
                _l2(
                    "default.technology.projects",
                    "项目文档",
                    "研发项目计划、需求、方案和复盘资料。",
                    [
                        _leaf(
                            "default.technology.projects.requirements",
                            "需求说明",
                            "产品需求、业务需求和需求变更说明。",
                            ["需求", "PRD", "变更", "用户故事"],
                        ),
                        _leaf(
                            "default.technology.projects.retrospective",
                            "项目复盘",
                            "里程碑、复盘、问题清单和改进措施。",
                            ["复盘", "里程碑", "问题清单", "改进"],
                        ),
                    ],
                ),
            ],
        ),
        _l1(
            "default.operations",
            "运营、销售与服务",
            "市场销售、客户服务、行政办公、采购供应链和项目运营文档。",
            [
                _l2(
                    "default.operations.sales",
                    "销售与市场",
                    "销售资料、市场活动和客户方案。",
                    [
                        _leaf(
                            "default.operations.sales.playbook",
                            "销售手册",
                            "销售流程、话术、客户画像和竞争分析。",
                            ["销售", "话术", "客户画像", "竞争分析"],
                        ),
                        _leaf(
                            "default.operations.sales.campaign",
                            "市场活动",
                            "活动方案、品牌内容、投放计划和复盘。",
                            ["市场", "活动", "投放", "品牌"],
                        ),
                    ],
                ),
                _l2(
                    "default.operations.service",
                    "客户服务与售后",
                    "客户支持、售后维修和服务标准。",
                    [
                        _leaf(
                            "default.operations.service.sop",
                            "服务流程",
                            "客服处理流程、工单流转和响应标准。",
                            ["客服", "工单", "SLA", "响应"],
                        ),
                        _leaf(
                            "default.operations.service.after_sales",
                            "售后维修",
                            "售后维修、备件、更换和现场服务记录。",
                            ["售后", "维修", "备件", "现场服务"],
                        ),
                    ],
                ),
            ],
        ),
        _l1(
            "default.it_quality",
            "IT、安全与质量",
            "信息安全、IT 运维、质量、安全生产和审计相关文档。",
            [
                _l2(
                    "default.it_quality.security",
                    "IT 与信息安全",
                    "账号权限、系统运维、信息安全和隐私保护。",
                    [
                        _leaf(
                            "default.it_quality.security.access",
                            "账号与权限",
                            "账号申请、权限审批、访问控制和权限回收。",
                            ["账号", "权限", "访问控制", "审批"],
                        ),
                        _leaf(
                            "default.it_quality.security.incident",
                            "安全事件",
                            "安全事件响应、漏洞、告警和整改报告。",
                            ["安全事件", "漏洞", "告警", "整改"],
                        ),
                    ],
                ),
                _l2(
                    "default.it_quality.quality",
                    "质量、安全与审计",
                    "质量管理、安全生产、检查和审计。",
                    [
                        _leaf(
                            "default.it_quality.quality.inspection",
                            "质量检验",
                            "质量检验标准、抽检记录和缺陷分析。",
                            ["质量", "检验", "抽检", "缺陷"],
                        ),
                        _leaf(
                            "default.it_quality.quality.safety",
                            "安全生产",
                            "安全生产制度、培训、事故和隐患排查。",
                            ["安全生产", "培训", "事故", "隐患"],
                        ),
                    ],
                ),
            ],
        ),
    ]

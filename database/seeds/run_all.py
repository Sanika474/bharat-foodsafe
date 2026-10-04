import os
import sys
import uuid
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.core.database import SessionLocal
from app.models.identity import Permission, Restaurant, Role, RolePermission, User
from app.models.tasks_and_rules import RuleSource, TaskCategory


def seed_roles_and_permissions(db):
    print("Seeding system roles and permissions...")
    roles_data = [
        {"name": "STAFF", "description": "Kitchen Staff Member executing tasks", "is_system_role": True},
        {"name": "MANAGER", "description": "Kitchen Manager overseeing operations & incidents", "is_system_role": True},
        {"name": "PLATFORM_ADMIN", "description": "Platform System Administrator", "is_system_role": True},
    ]

    roles_map = {}
    for r in roles_data:
        role = db.query(Role).filter_by(name=r["name"]).first()
        if not role:
            role = Role(
                id=uuid.uuid4(),
                name=r["name"],
                description=r["description"],
                is_system_role=r["is_system_role"],
            )
            db.add(role)
            db.flush()
            print(f"  Created role: {role.name}")
        else:
            print(f"  Role already exists: {role.name}")
        roles_map[role.name] = role

    permissions_data = [
        {"resource": "task", "action": "read"},
        {"resource": "task", "action": "create"},
        {"resource": "task", "action": "update"},
        {"resource": "task", "action": "delete"},
        {"resource": "incident", "action": "read"},
        {"resource": "incident", "action": "create"},
        {"resource": "incident", "action": "verify"},
        {"resource": "rule", "action": "read"},
        {"resource": "rule", "action": "create"},
        {"resource": "rule", "action": "verify"},
        {"resource": "user", "action": "read"},
        {"resource": "user", "action": "create"},
        {"resource": "user", "action": "update"},
        {"resource": "user", "action": "delete"},
    ]

    permissions_map = {}
    for p in permissions_data:
        perm = db.query(Permission).filter_by(resource=p["resource"], action=p["action"]).first()
        if not perm:
            perm = Permission(
                id=uuid.uuid4(),
                resource=p["resource"],
                action=p["action"],
            )
            db.add(perm)
            db.flush()
            print(f"  Created permission: {perm.resource}:{perm.action}")
        permissions_map[f"{perm.resource}:{perm.action}"] = perm

    # Role Permissions Mapping
    role_perm_mappings = {
        "STAFF": [
            "task:read", "task:update", "incident:read", "rule:read"
        ],
        "MANAGER": [
            "task:read", "task:create", "task:update", "task:delete",
            "incident:read", "incident:create", "incident:verify",
            "rule:read", "user:read", "user:create", "user:update"
        ],
        "PLATFORM_ADMIN": [
            "task:read", "task:create", "task:update", "task:delete",
            "incident:read", "incident:create", "incident:verify",
            "rule:read", "rule:create", "rule:verify",
            "user:read", "user:create", "user:update", "user:delete"
        ]
    }

    for role_name, perm_keys in role_perm_mappings.items():
        role = roles_map.get(role_name)
        if not role:
            continue
        for perm_key in perm_keys:
            perm = permissions_map.get(perm_key)
            if not perm:
                continue
            existing = db.query(RolePermission).filter_by(role_id=role.id, permission_id=perm.id).first()
            if not existing:
                rp = RolePermission(
                    id=uuid.uuid4(),
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(rp)


def seed_demo_tenant(db):
    print("Seeding demo restaurant tenant...")
    restaurant = db.query(Restaurant).filter_by(name="Demo Commercial Kitchen").first()
    if not restaurant:
        restaurant = Restaurant(
            id=uuid.uuid4(),
            name="Demo Commercial Kitchen",
            legal_name="Bharat FoodSafe Demo Operations Pvt Ltd",
            category="RESTAURANT",
            address_line1="100 Feet Road, Indiranagar",
            city="Bengaluru",
            state="Karnataka",
            pincode="560001",
            phone="08012345678",
            email="demo@bharatfoodsafe.in",
            timezone="Asia/Kolkata",
            status="ACTIVE",
        )
        db.add(restaurant)
        db.flush()
        print(f"  Created demo restaurant: {restaurant.name} (ID: {restaurant.id})")
    else:
        print(f"  Demo restaurant already exists: {restaurant.name}")

    return restaurant


def seed_reference_data(db, restaurant):
    print("Seeding reference task categories and rule sources...")

    categories_data = [
        {"name": "Temperature Logging", "code": "TEMP_LOG", "description": "Cold storage, hot holding, and cooking core temperature checks", "sort_order": 1},
        {"name": "Hygiene & Sanitation", "code": "HYGIENE", "description": "Handwashing, surface sanitization, and pest control checks", "sort_order": 2},
        {"name": "Raw Material Receiving", "code": "RECEIVING", "description": "Supplier delivery inspection, batch verification, and packaging checks", "sort_order": 3},
    ]

    for cat_data in categories_data:
        cat = db.query(TaskCategory).filter_by(code=cat_data["code"]).first()
        if not cat:
            cat = TaskCategory(
                id=uuid.uuid4(),
                restaurant_id=restaurant.id if restaurant else None,
                name=cat_data["name"],
                code=cat_data["code"],
                description=cat_data["description"],
                sort_order=cat_data["sort_order"],
                is_active=True,
            )
            db.add(cat)
            print(f"  Created task category: {cat.name}")

    rule_source = db.query(RuleSource).filter_by(source_code="FSSAI_SCHEDULE_4").first()
    if not rule_source:
        rule_source = RuleSource(
            id=uuid.uuid4(),
            source_code="FSSAI_SCHEDULE_4",
            title="FSSAI Schedule 4 Food Safety & Hygiene Requirements",
            issuing_authority="FSSAI",
            document_reference="FSSAI/SOP/2026/01",
            effective_date=datetime.now(timezone.utc),
            review_status="VERIFIED",
            verified_at=datetime.now(timezone.utc),
        )
        db.add(rule_source)
        print(f"  Created verified rule source: {rule_source.title}")


def run_seeds():
    db = SessionLocal()
    try:
        print("Starting seed script execution...")
        seed_roles_and_permissions(db)
        demo_restaurant = seed_demo_tenant(db)
        seed_reference_data(db, demo_restaurant)
        db.commit()
        print("Seed data script executed successfully with 0 errors!")
    except Exception as e:
        db.rollback()
        print(f"Error during seed execution: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_seeds()

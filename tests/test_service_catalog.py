from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    DUPLICATE_SERVICE_ID_IN_PAYLOAD,
    MISSING_AUTH_TOKEN,
    SUPPORT_PRICE_CANNOT_BE_NULL,
    VALIDATION_ERROR_MESSAGE,
)
from app.modules.customers.schemas import Customer
from app.modules.users.schemas import User


def _create_customer_entity(db_session: Session) -> Customer:
    customer = Customer(
        name="Tehran Customer",
        grade=1,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def _create_admin(db_session: Session) -> User:
    admin = User(
        full_name="Main Admin",
        mobile="09120000000",
        role=UserRole.ADMIN,
        customer_id=None,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _create_customer_user(db_session: Session, customer_id: int) -> User:
    customer = User(
        full_name="Customer One",
        mobile="09123334455",
        role=UserRole.CUSTOMER,
        customer_id=customer_id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def _login(client: TestClient, mobile: str) -> str:
    request_response = client.post("/auth/request-otp", json={"mobile": mobile})
    otp_code = request_response.json()["dev_otp"]
    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": mobile, "otp_code": otp_code},
    )
    return verify_response.json()["access_token"]


def _admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = _create_admin(db_session=db_session)
    token = _login(client=client, mobile=admin.mobile)
    return {"Authorization": f"Bearer {token}"}


def _create_service_project(
    client: TestClient,
    headers: dict[str, str],
    *,
    code: str | None = None,
    name: str,
    sort_order: int = 10,
) -> int:
    del code
    response = client.post(
        "/service-projects",
        headers=headers,
        json={
            "name": name,
            "description": f"{name} project",
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_service_group(
    client: TestClient,
    headers: dict[str, str],
    *,
    code: str | None = None,
    name: str,
    project_id: int | None = None,
    sort_order: int = 10,
) -> int:
    del code, project_id
    response = client.post(
        "/service-groups",
        headers=headers,
        json={
            "name": name,
            "description": f"{name} services",
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_service(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_id: int | None = None,
    group_id: int,
    code: str | None = None,
    name: str,
    sort_order: int = 10,
) -> int:
    resolved_project_id = project_id or _create_service_project(
        client=client,
        headers=headers,
        name=f"{name} Project",
        sort_order=sort_order,
    )
    del code
    response = client.post(
        "/services",
        headers=headers,
        json={
            "project_id": resolved_project_id,
            "group_id": group_id,
            "name": name,
            "description": f"{name} description",
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_service_group(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    response = client.post(
        "/service-groups",
        headers=headers,
        json={
            "name": "Security",
            "description": "Security services",
            "sort_order": 1,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "code" not in data
    assert data["name"] == "Security"
    assert data["is_active"] is True


def test_create_service_project(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    response = client.post(
        "/service-projects",
        headers=headers,
        json={
            "name": "Smart City",
            "description": "Smart city umbrella project",
            "sort_order": 1,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Smart City"
    assert data["is_active"] is True


def test_service_project_list_supports_search_sort_and_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    _create_service_project(
        client=client,
        headers=headers,
        name="Core Project",
        sort_order=1,
    )
    _create_service_project(
        client=client,
        headers=headers,
        name="Support Project",
        sort_order=2,
    )
    _create_service_project(
        client=client,
        headers=headers,
        name="Billing Project",
        sort_order=3,
    )

    search_response = client.get(
        "/service-projects",
        headers=headers,
        params={"search": "support"},
    )
    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data["total_page"] == 1
    assert len(search_data["items"]) == 1
    assert search_data["items"][0]["name"] == "Support Project"
    assert search_response.headers["X-Total-Count"] == "1"

    paged_response = client.get(
        "/service-projects",
        headers=headers,
        params={
            "sort_by": "name",
            "sort_order": "asc",
            "page": 1,
            "page_size": 2,
        },
    )
    assert paged_response.status_code == 200
    paged_data = paged_response.json()
    assert paged_data["total_page"] == 2
    assert len(paged_data["items"]) == 2
    assert paged_data["items"][0]["name"] == "Billing Project"
    assert paged_data["items"][1]["name"] == "Core Project"
    assert paged_response.headers["X-Total-Count"] == "3"
    assert paged_response.headers["X-Total-Pages"] == "2"


def test_get_all_service_projects_returns_all_items_without_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    _create_service_project(
        client=client,
        headers=headers,
        name="Core Project",
        sort_order=1,
    )
    _create_service_project(
        client=client,
        headers=headers,
        name="Support Project",
        sort_order=2,
    )
    _create_service_project(
        client=client,
        headers=headers,
        name="Billing Project",
        sort_order=3,
    )

    response = client.get("/service-projects/all", headers=headers)
    assert response.status_code == 200

    items = response.json()
    assert len(items) == 3
    assert [item["name"] for item in items] == [
        "Core Project",
        "Support Project",
        "Billing Project",
    ]


def test_update_and_deactivate_service_project(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    project_id = _create_service_project(
        client=client,
        headers=headers,
        name="Base Project",
    )

    update_response = client.patch(
        f"/service-projects/{project_id}",
        headers=headers,
        json={
            "name": "Updated Project",
            "sort_order": 20,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Project"
    assert update_response.json()["sort_order"] == 20

    deactivate_response = client.delete(f"/service-projects/{project_id}", headers=headers)
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False


def test_update_service_group(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="taxes",
        name="Taxes",
    )

    response = client.patch(
        f"/service-groups/{group_id}",
        headers=headers,
        json={"name": "Tax Services", "sort_order": 20},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tax Services"
    assert data["sort_order"] == 20


def test_duplicate_service_group_name_is_allowed(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    first_response = client.post(
        "/service-groups",
        headers=headers,
        json={
            "name": "Shared Group",
            "description": None,
            "sort_order": 1,
        },
    )
    second_response = client.post(
        "/service-groups",
        headers=headers,
        json={
            "name": "Shared Group",
            "description": None,
            "sort_order": 2,
        },
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201


def test_deactivate_service_group(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="renovation",
        name="Renovation",
    )

    response = client.delete(f"/service-groups/{group_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_create_service_under_group_and_filter_by_group(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    security_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="security-project",
        name="Security Project",
        sort_order=1,
    )
    infra_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="infrastructure-project",
        name="Infrastructure Project",
        sort_order=2,
    )
    security_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=security_project_id,
        code="security",
        name="Security",
    )
    infra_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=infra_project_id,
        code="infrastructure",
        name="Infrastructure",
    )

    _create_service(
        client=client,
        headers=headers,
        project_id=security_project_id,
        group_id=security_group_id,
        code="camera-monitoring",
        name="Camera Monitoring",
    )
    _create_service(
        client=client,
        headers=headers,
        project_id=infra_project_id,
        group_id=infra_group_id,
        code="fiber-upgrade",
        name="Fiber Upgrade",
    )

    response = client.get(
        "/services",
        headers=headers,
        params={"group_id": security_group_id},
    )
    assert response.status_code == 200
    services = response.json()
    assert services["total_page"] == 1
    assert len(services["items"]) == 1
    assert services["items"][0]["group_id"] == security_group_id
    assert services["items"][0]["project_id"] == security_project_id
    assert services["items"][0]["group"]["name"] == "Security"
    assert services["items"][0]["project"]["name"] == "Security Project"

    project_filtered_response = client.get(
        "/services",
        headers=headers,
        params={"project_id": infra_project_id},
    )
    assert project_filtered_response.status_code == 200
    project_filtered_services = project_filtered_response.json()
    assert project_filtered_services["total_page"] == 1
    assert len(project_filtered_services["items"]) == 1
    assert project_filtered_services["items"][0]["project_id"] == infra_project_id


def test_update_service_group_assignment(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    first_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="misc-project",
        name="Misc Project",
    )
    second_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="support-project",
        name="Support Project",
    )
    first_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=first_project_id,
        code="miscellaneous",
        name="Miscellaneous",
    )
    second_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=second_project_id,
        code="support",
        name="Support",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        project_id=first_project_id,
        group_id=first_group_id,
        code="hotline",
        name="Hotline",
    )

    response = client.patch(
        f"/services/{service_id}",
        headers=headers,
        json={"project_id": second_project_id, "group_id": second_group_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["group_id"] == second_group_id
    assert data["project_id"] == second_project_id
    assert data["group"]["id"] == second_group_id
    assert data["project"]["id"] == second_project_id


def test_duplicate_service_name_is_allowed(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    project_id = _create_service_project(
        client=client,
        headers=headers,
        code="duplicate-service-code-project",
        name="Duplicate Service Code Project",
    )
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="duplicate-service-code-group",
        name="Duplicate Service Code Group",
    )

    first_response = client.post(
        "/services",
        headers=headers,
        json={
            "project_id": project_id,
            "group_id": group_id,
            "name": "Shared Service",
            "description": None,
            "sort_order": 1,
        },
    )
    second_response = client.post(
        "/services",
        headers=headers,
        json={
            "project_id": project_id,
            "group_id": group_id,
            "name": "Shared Service",
            "description": None,
            "sort_order": 2,
        },
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201


def test_deactivate_service(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="other",
        name="Other",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="general-service",
        name="General Service",
    )

    response = client.delete(f"/services/{service_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_service_group_and_service_lists_support_search_sort_and_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    core_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="core-project",
        name="Core Project",
        sort_order=1,
    )
    support_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="support-project",
        name="Support Project",
        sort_order=2,
    )
    security_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=core_project_id,
        code="security",
        name="Security",
        sort_order=1,
    )
    ops_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=core_project_id,
        code="operations",
        name="Operations",
        sort_order=2,
    )
    _create_service_group(
        client=client,
        headers=headers,
        project_id=support_project_id,
        code="support",
        name="Support",
        sort_order=3,
    )

    group_search = client.get(
        "/service-groups",
        headers=headers,
        params={"search": "oper"},
    )
    assert group_search.status_code == 200
    group_search_data = group_search.json()
    assert group_search_data["total_page"] == 1
    assert len(group_search_data["items"]) == 1
    assert group_search_data["items"][0]["name"] == "Operations"
    assert group_search.headers["X-Total-Count"] == "1"

    group_paged = client.get(
        "/service-groups",
        headers=headers,
        params={
            "sort_by": "name",
            "sort_order": "asc",
            "page": 1,
            "page_size": 2,
        },
    )
    assert group_paged.status_code == 200
    group_paged_data = group_paged.json()
    assert group_paged_data["total_page"] == 2
    assert len(group_paged_data["items"]) == 2
    assert group_paged.headers["X-Total-Count"] == "3"
    assert group_paged.headers["X-Total-Pages"] == "2"

    _create_service(
        client=client,
        headers=headers,
        project_id=core_project_id,
        group_id=security_group_id,
        code="alpha-service",
        name="Alpha Service",
        sort_order=1,
    )
    _create_service(
        client=client,
        headers=headers,
        project_id=core_project_id,
        group_id=ops_group_id,
        code="gamma-service",
        name="Gamma Service",
        sort_order=2,
    )
    _create_service(
        client=client,
        headers=headers,
        project_id=core_project_id,
        group_id=ops_group_id,
        code="beta-service",
        name="Beta Service",
        sort_order=3,
    )

    service_search = client.get(
        "/services",
        headers=headers,
        params={"search": "beta"},
    )
    assert service_search.status_code == 200
    service_search_data = service_search.json()
    assert service_search_data["total_page"] == 1
    assert len(service_search_data["items"]) == 1
    assert service_search_data["items"][0]["name"] == "Beta Service"
    assert service_search.headers["X-Total-Count"] == "1"

    project_service_search = client.get(
        "/services",
        headers=headers,
        params={"project_id": core_project_id},
    )
    assert project_service_search.status_code == 200
    project_service_search_data = project_service_search.json()
    assert project_service_search_data["total_page"] == 1
    assert len(project_service_search_data["items"]) == 3

    service_paged = client.get(
        "/services",
        headers=headers,
        params={
            "sort_by": "name",
            "sort_order": "desc",
            "page": 1,
            "page_size": 2,
        },
    )
    assert service_paged.status_code == 200
    service_items = service_paged.json()
    assert service_items["total_page"] == 2
    assert len(service_items["items"]) == 2
    assert service_items["items"][0]["name"] == "Gamma Service"
    assert service_items["items"][1]["name"] == "Beta Service"
    assert service_paged.headers["X-Total-Count"] == "3"
    assert service_paged.headers["X-Total-Pages"] == "2"


def test_get_all_service_groups_returns_all_items_without_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    _create_service_group(
        client=client,
        headers=headers,
        code="security",
        name="Security",
        sort_order=1,
    )
    _create_service_group(
        client=client,
        headers=headers,
        code="operations",
        name="Operations",
        sort_order=2,
    )
    _create_service_group(
        client=client,
        headers=headers,
        code="support",
        name="Support",
        sort_order=3,
    )

    response = client.get("/service-groups/all", headers=headers)
    assert response.status_code == 200

    items = response.json()
    assert len(items) == 3
    assert [item["name"] for item in items] == [
        "Security",
        "Operations",
        "Support",
    ]


def test_service_project_hierarchy_lists_groups_and_services_by_project(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    first_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="first-hierarchy-project",
        name="First Hierarchy Project",
        sort_order=1,
    )
    second_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="second-hierarchy-project",
        name="Second Hierarchy Project",
        sort_order=2,
    )
    shared_group_id = _create_service_group(
        client=client,
        headers=headers,
        code="shared-hierarchy-group",
        name="Shared Hierarchy Group",
        sort_order=1,
    )

    _create_service(
        client=client,
        headers=headers,
        project_id=first_project_id,
        group_id=shared_group_id,
        code="first-project-service",
        name="First Project Service",
        sort_order=1,
    )
    _create_service(
        client=client,
        headers=headers,
        project_id=second_project_id,
        group_id=shared_group_id,
        code="second-project-service",
        name="Second Project Service",
        sort_order=1,
    )

    response = client.get("/service-projects/hierarchy", headers=headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2

    item_map = {item["id"]: item for item in items}
    first_project = item_map[first_project_id]
    second_project = item_map[second_project_id]

    assert len(first_project["groups"]) == 1
    assert first_project["groups"][0]["name"] == "Shared Hierarchy Group"
    assert first_project["groups"][0]["services"][0]["name"] == "First Project Service"

    assert len(second_project["groups"]) == 1
    assert second_project["groups"][0]["name"] == "Shared Hierarchy Group"
    assert second_project["groups"][0]["services"][0]["name"] == "Second Project Service"

    filtered_response = client.get(
        "/service-projects/hierarchy",
        headers=headers,
        params={"project_id": second_project_id},
    )
    assert filtered_response.status_code == 200
    filtered_items = filtered_response.json()
    assert len(filtered_items) == 1
    assert filtered_items[0]["id"] == second_project_id
    assert filtered_items[0]["groups"][0]["services"][0]["name"] == "Second Project Service"


def test_create_customer_service_config_and_list(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    project_id = _create_service_project(
        client=client,
        headers=headers,
        code="security-project",
        name="Security Project",
    )
    group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=project_id,
        code="security",
        name="Security",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        project_id=project_id,
        group_id=group_id,
        code="guarding",
        name="Guarding",
    )

    upsert_response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 4000000,
                    "support_price": 800000,
                    "notes": "Initial setup",
                }
            ]
        },
    )
    assert upsert_response.status_code == 200
    upsert_data = upsert_response.json()
    assert len(upsert_data) == 1
    assert upsert_data[0]["customer_id"] == customer.id
    assert upsert_data[0]["service_id"] == service_id
    assert upsert_data[0]["project_id"] == project_id
    assert upsert_data[0]["group_id"] == group_id
    assert upsert_data[0]["sale_price"] == 4000000
    assert upsert_data[0]["support_price"] == 800000

    list_response = client.get(f"/customers/{customer.id}/services", headers=headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total_page"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["project_name"] == "Security Project"
    assert list_data["items"][0]["group_name"] == "Security"


def test_customer_service_list_supports_filter_search_sort_and_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    project_id = _create_service_project(
        client=client,
        headers=headers,
        code="ops-project",
        name="Operations Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=project_id,
        code="ops",
        name="Operations",
        sort_order=1,
    )
    service_a = _create_service(
        client=client,
        headers=headers,
        project_id=project_id,
        group_id=group_id,
        code="guard",
        name="Guard",
        sort_order=1,
    )
    service_b = _create_service(
        client=client,
        headers=headers,
        project_id=project_id,
        group_id=group_id,
        code="camera",
        name="Camera",
        sort_order=2,
    )
    service_c = _create_service(
        client=client,
        headers=headers,
        project_id=project_id,
        group_id=group_id,
        code="fiber",
        name="Fiber",
        sort_order=3,
    )

    upsert_response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_a,
                    "is_enabled": True,
                    "sale_price": 1000,
                    "support_price": 100,
                    "notes": "guard enabled",
                },
                {
                    "service_id": service_b,
                    "is_enabled": False,
                    "sale_price": 2000,
                    "support_price": 200,
                    "notes": "camera disabled",
                },
                {
                    "service_id": service_c,
                    "is_enabled": True,
                    "sale_price": 3000,
                    "support_price": 0,
                    "notes": "fiber enabled",
                },
            ]
        },
    )
    assert upsert_response.status_code == 200

    filtered_response = client.get(
        f"/customers/{customer.id}/services",
        headers=headers,
        params={
            "is_enabled": True,
            "search": "fib",
        },
    )
    assert filtered_response.status_code == 200
    filtered_items = filtered_response.json()
    assert filtered_items["total_page"] == 1
    assert len(filtered_items["items"]) == 1
    assert filtered_items["items"][0]["project_id"] == project_id
    assert filtered_items["items"][0]["service_name"] == "Fiber"
    assert filtered_response.headers["X-Total-Count"] == "1"

    project_filtered_response = client.get(
        f"/customers/{customer.id}/services",
        headers=headers,
        params={"project_id": project_id},
    )
    assert project_filtered_response.status_code == 200
    project_filtered_data = project_filtered_response.json()
    assert project_filtered_data["total_page"] == 1
    assert len(project_filtered_data["items"]) == 3

    paged_response = client.get(
        f"/customers/{customer.id}/services",
        headers=headers,
        params={
            "sort_by": "sale_price",
            "sort_order": "desc",
            "page": 1,
            "page_size": 2,
        },
    )
    assert paged_response.status_code == 200
    paged_items = paged_response.json()
    assert paged_items["total_page"] == 2
    assert len(paged_items["items"]) == 2
    assert paged_items["items"][0]["sale_price"] == 3000
    assert paged_items["items"][1]["sale_price"] == 2000
    assert paged_response.headers["X-Total-Count"] == "3"
    assert paged_response.headers["X-Total-Pages"] == "2"


def test_bulk_upsert_customer_service_configs_omitted_items_remain_unchanged(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="operations",
        name="Operations",
    )

    service_a = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="ops-a",
        name="Ops A",
    )
    service_b = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="ops-b",
        name="Ops B",
    )
    service_c = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="ops-c",
        name="Ops C",
    )

    first_upsert = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_a,
                    "is_enabled": True,
                    "sale_price": 1000000,
                    "support_price": 100000,
                    "notes": "A1",
                },
                {
                    "service_id": service_b,
                    "is_enabled": True,
                    "sale_price": 2000000,
                    "support_price": 200000,
                    "notes": "B1",
                },
            ]
        },
    )
    assert first_upsert.status_code == 200

    second_upsert = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_a,
                    "is_enabled": True,
                    "sale_price": 1100000,
                    "support_price": 120000,
                    "notes": "A2",
                },
                {
                    "service_id": service_c,
                    "is_enabled": True,
                    "sale_price": 3000000,
                    "support_price": 0,
                    "notes": "C1",
                },
            ]
        },
    )
    assert second_upsert.status_code == 200

    list_response = client.get(f"/customers/{customer.id}/services", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 3

    item_map = {item["service_id"]: item for item in items}
    assert item_map[service_a]["sale_price"] == 1100000
    assert item_map[service_b]["sale_price"] == 2000000
    assert item_map[service_c]["sale_price"] == 3000000
    assert item_map[service_b]["support_price"] == 200000


def test_duplicate_customer_service_pair_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="duplicate-check",
        name="Duplicate Check",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="duplicate-service",
        name="Duplicate Service",
    )

    response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 1000,
                    "support_price": 0,
                    "notes": None,
                },
                {
                    "service_id": service_id,
                    "is_enabled": False,
                    "sale_price": 1200,
                    "support_price": 0,
                    "notes": None,
                },
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["message"] == DUPLICATE_SERVICE_ID_IN_PAYLOAD
    assert response.json()["detail"] == DUPLICATE_SERVICE_ID_IN_PAYLOAD
    assert response.json()["developer_message"] == "The payload contains duplicate service_id values."


def test_support_price_is_required(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="required-support",
        name="Required Support",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="required-support-service",
        name="Required Support Service",
    )

    response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 100,
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["message"] == VALIDATION_ERROR_MESSAGE
    assert response.json()["detail"][0]["msg"] == "\u0627\u06cc\u0646 \u0641\u06cc\u0644\u062f \u0627\u0644\u0632\u0627\u0645\u06cc \u0627\u0633\u062a."


def test_negative_sale_price_is_rejected(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="negative-sale",
        name="Negative Sale",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="negative-sale-service",
        name="Negative Sale Service",
    )

    response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": -1,
                    "support_price": 100,
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["message"] == VALIDATION_ERROR_MESSAGE
    assert response.json()["detail"][0]["msg"] == "\u0645\u0642\u062f\u0627\u0631 \u0628\u0627\u06cc\u062f \u0628\u0632\u0631\u06af \u062a\u0631 \u06cc\u0627 \u0645\u0633\u0627\u0648\u06cc 0 \u0628\u0627\u0634\u062f."


def test_sale_price_can_be_omitted(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="optional-sale",
        name="Optional Sale",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="optional-sale-service",
        name="Optional Sale Service",
    )

    response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "support_price": 2500,
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()[0]["sale_price"] is None


def test_negative_support_price_is_rejected(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="negative-support",
        name="Negative Support",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="negative-support-service",
        name="Negative Support Service",
    )

    response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 2500,
                    "support_price": -10,
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 422


def test_patch_single_customer_service_config(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="patchable-group",
        name="Patchable Group",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="patchable-service",
        name="Patchable Service",
    )

    create_response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 1000,
                    "support_price": 200,
                    "notes": "v1",
                }
            ]
        },
    )
    assert create_response.status_code == 200
    config_id = create_response.json()[0]["id"]

    patch_response = client.patch(
        f"/customer-service-configs/{config_id}",
        headers=headers,
        json={
            "is_enabled": False,
            "sale_price": None,
            "support_price": 250,
            "notes": "v2",
        },
    )
    assert patch_response.status_code == 200
    patch_data = patch_response.json()
    assert patch_data["is_enabled"] is False
    assert patch_data["sale_price"] is None
    assert patch_data["support_price"] == 250
    assert patch_data["notes"] == "v2"


def test_patch_single_customer_service_config_rejects_null_support_price(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="patch-null-support-group",
        name="Patch Null Support Group",
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        group_id=group_id,
        code="patch-null-support-service",
        name="Patch Null Support Service",
    )

    create_response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 1000,
                    "support_price": 200,
                    "notes": "v1",
                }
            ]
        },
    )
    assert create_response.status_code == 200
    config_id = create_response.json()[0]["id"]

    patch_response = client.patch(
        f"/customer-service-configs/{config_id}",
        headers=headers,
        json={
            "support_price": None,
        },
    )
    assert patch_response.status_code == 422
    assert patch_response.json()["detail"] == SUPPORT_PRICE_CANNOT_BE_NULL


def test_pricing_summary_returns_grouped_totals_and_ignores_disabled(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    security_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="security-project",
        name="Security Project",
        sort_order=1,
    )
    infra_project_id = _create_service_project(
        client=client,
        headers=headers,
        code="infrastructure-project",
        name="Infrastructure Project",
        sort_order=2,
    )

    security_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=security_project_id,
        code="security",
        name="Security",
        sort_order=1,
    )
    infra_group_id = _create_service_group(
        client=client,
        headers=headers,
        project_id=infra_project_id,
        code="infrastructure",
        name="Infrastructure",
        sort_order=2,
    )

    service_guard = _create_service(
        client=client,
        headers=headers,
        project_id=security_project_id,
        group_id=security_group_id,
        code="guard",
        name="Guard",
    )
    service_camera = _create_service(
        client=client,
        headers=headers,
        project_id=security_project_id,
        group_id=security_group_id,
        code="camera",
        name="Camera",
    )
    service_fiber = _create_service(
        client=client,
        headers=headers,
        project_id=infra_project_id,
        group_id=infra_group_id,
        code="fiber",
        name="Fiber",
    )

    upsert_response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_guard,
                    "is_enabled": True,
                    "sale_price": 100,
                    "support_price": 20,
                    "notes": None,
                },
                {
                    "service_id": service_camera,
                    "is_enabled": False,
                    "sale_price": 200,
                    "support_price": 30,
                    "notes": None,
                },
                {
                    "service_id": service_fiber,
                    "is_enabled": True,
                    "sale_price": 300,
                    "support_price": 0,
                    "notes": None,
                },
            ]
        },
    )
    assert upsert_response.status_code == 200

    summary_response = client.get(
        f"/customers/{customer.id}/pricing-summary",
        headers=headers,
    )
    assert summary_response.status_code == 200
    summary_data = summary_response.json()

    assert summary_data["totals"]["sale_total"] == 400
    assert summary_data["totals"]["support_total"] == 20
    assert summary_data["totals"]["grand_total"] == 420

    groups = summary_data["groups"]
    assert len(groups) == 2
    group_map = {item["group_name"]: item for item in groups}

    assert group_map["Security"]["project_id"] == security_project_id
    assert group_map["Security"]["project_name"] == "Security Project"
    assert group_map["Security"]["totals"]["sale_total"] == 100
    assert group_map["Security"]["totals"]["support_total"] == 20
    assert group_map["Security"]["totals"]["grand_total"] == 120
    assert group_map["Infrastructure"]["project_id"] == infra_project_id
    assert group_map["Infrastructure"]["project_name"] == "Infrastructure Project"
    assert group_map["Infrastructure"]["totals"]["sale_total"] == 300
    assert group_map["Infrastructure"]["totals"]["support_total"] == 0
    assert group_map["Infrastructure"]["totals"]["grand_total"] == 300

    security_items = {item["service_name"]: item for item in group_map["Security"]["items"]}
    assert security_items["Camera"]["line_sale_total"] == 0
    assert security_items["Camera"]["line_support_total"] == 0
    assert security_items["Camera"]["line_grand_total"] == 0

    infra_items = {item["service_name"]: item for item in group_map["Infrastructure"]["items"]}
    assert infra_items["Fiber"]["support_price"] == 0
    assert infra_items["Fiber"]["line_support_total"] == 0


def test_admin_only_access_enforced_and_customer_access_denied(
    client: TestClient,
    db_session: Session,
) -> None:
    customer_entity = _create_customer_entity(db_session=db_session)
    customer_user = _create_customer_user(db_session=db_session, customer_id=customer_entity.id)
    customer_token = _login(client=client, mobile=customer_user.mobile)
    headers = _admin_headers(client=client, db_session=db_session)

    unauthorized_response = client.post(
        "/service-groups",
        json={
            "name": "Unauthorized",
            "description": None,
            "sort_order": 1,
        },
    )
    assert unauthorized_response.status_code == 401
    assert unauthorized_response.json()["message"] == MISSING_AUTH_TOKEN
    assert unauthorized_response.json()["detail"] == MISSING_AUTH_TOKEN
    assert unauthorized_response.json()["developer_message"] == "Authorization bearer token was not provided."

    customer_response = client.post(
        "/service-groups",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "name": "Denied",
            "description": None,
            "sort_order": 1,
        },
    )
    assert customer_response.status_code == 403
    assert customer_response.json()["message"] == ADMIN_ACCESS_REQUIRED
    assert customer_response.json()["detail"] == ADMIN_ACCESS_REQUIRED
    assert customer_response.json()["developer_message"] == "Authenticated user does not have admin role."



def test_inactive_service_catalog_records_are_hidden_from_get_apis(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(db_session=db_session)
    project_id = _create_service_project(
        client=client,
        headers=headers,
        name="Hidden Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=headers,
        code="hidden-group",
        name="Hidden Group",
        sort_order=1,
    )
    service_id = _create_service(
        client=client,
        headers=headers,
        project_id=project_id,
        group_id=group_id,
        code="hidden-service",
        name="Hidden Service",
        sort_order=1,
    )

    upsert_response = client.put(
        f"/customers/{customer.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "sale_price": 1500,
                    "support_price": 150,
                    "notes": "hidden later",
                }
            ]
        },
    )
    assert upsert_response.status_code == 200

    deactivate_service_response = client.delete(f"/services/{service_id}", headers=headers)
    assert deactivate_service_response.status_code == 200

    service_list_response = client.get(
        "/services",
        headers=headers,
        params={"project_id": project_id},
    )
    assert service_list_response.status_code == 200
    assert service_list_response.headers["X-Total-Count"] == "0"
    assert service_list_response.json()["items"] == []

    service_detail_response = client.get(f"/services/{service_id}", headers=headers)
    assert service_detail_response.status_code == 404

    customer_services_response = client.get(f"/customers/{customer.id}/services", headers=headers)
    assert customer_services_response.status_code == 200
    assert customer_services_response.headers["X-Total-Count"] == "0"
    assert customer_services_response.json()["items"] == []

    pricing_summary_response = client.get(f"/customers/{customer.id}/pricing-summary", headers=headers)
    assert pricing_summary_response.status_code == 200
    pricing_summary_data = pricing_summary_response.json()
    assert pricing_summary_data["groups"] == []
    assert pricing_summary_data["totals"] == {
        "sale_total": 0,
        "support_total": 0,
        "grand_total": 0,
    }

    deactivate_group_response = client.delete(f"/service-groups/{group_id}", headers=headers)
    assert deactivate_group_response.status_code == 200

    group_list_response = client.get(
        "/service-groups",
        headers=headers,
        params={"search": "Hidden Group"},
    )
    assert group_list_response.status_code == 200
    assert group_list_response.headers["X-Total-Count"] == "0"
    assert group_list_response.json()["items"] == []

    group_all_response = client.get("/service-groups/all", headers=headers)
    assert group_all_response.status_code == 200
    assert group_all_response.json() == []

    group_detail_response = client.get(f"/service-groups/{group_id}", headers=headers)
    assert group_detail_response.status_code == 404

    deactivate_project_response = client.delete(f"/service-projects/{project_id}", headers=headers)
    assert deactivate_project_response.status_code == 200

    project_list_response = client.get(
        "/service-projects",
        headers=headers,
        params={"search": "Hidden Project"},
    )
    assert project_list_response.status_code == 200
    assert project_list_response.headers["X-Total-Count"] == "0"
    assert project_list_response.json()["items"] == []

    project_all_response = client.get("/service-projects/all", headers=headers)
    assert project_all_response.status_code == 200
    assert project_all_response.json() == []

    project_detail_response = client.get(f"/service-projects/{project_id}", headers=headers)
    assert project_detail_response.status_code == 404

    hierarchy_response = client.get("/service-projects/hierarchy", headers=headers)
    assert hierarchy_response.status_code == 200
    assert hierarchy_response.json() == []

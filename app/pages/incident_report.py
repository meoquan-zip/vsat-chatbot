import streamlit as st

from utils.db_crud import (
    create_incident,
    delete_incident,
    get_incident_by_id,
    list_incidents,
    resolve_incident,
)
from utils.email import init_incident_notifier
from utils.save_docs import (
    add_resolved_incident_to_vectordb,
    delete_incident_from_vectordb,
)

st.set_page_config(
    page_title="Incident Report - VSAT App",
    page_icon="🚨"
)
st.title("Incident Report")

# State for dialog
if "show_dialog" not in st.session_state:
    st.session_state["show_dialog"] = False
if "selected_incident_id" not in st.session_state:
    st.session_state["selected_incident_id"] = None

# Report new incident dialog
if st.session_state["show_dialog"]:
    with st.form("report_incident_form", clear_on_submit=True):
        st.subheader("Report New Incident")
        name = st.text_input("Name")
        description = st.text_area("Description", max_chars=1000)
        # leave SLA in minutes for testing purposes
        sla_no_of_hours = st.number_input("SLA time (minutes)", min_value=0.0, value=1.0, step=0.25, format="%.2f")
        email = st.text_input("Email")
        log = st.text_area("Log (optional)", max_chars=5000)
        submitted = st.form_submit_button("Submit")
        cancel = st.form_submit_button("Cancel")
        if submitted:
            missing_fields = []
            if not name:
                missing_fields.append("Name")
            if not description:
                missing_fields.append("Description")
            if not email:
                missing_fields.append("Email")
            if missing_fields:
                st.warning(f"Required field(s) missing: {', '.join(missing_fields)}.")
            else:
                incident = create_incident(
                    name,
                    description,
                    email,
                    log if log else None,
                    sla_no_of_hours
                )
                init_incident_notifier(incident.id)
                st.success("Incident reported!")
                st.session_state["show_dialog"] = False
                st.rerun()
        if cancel:
            st.session_state["show_dialog"] = False
            st.rerun()

# Top bar with button
col1, col2 = st.columns([1, 5])
with col2:
    st.write("")
with col1:
    if st.button("Report New Incident", key="report_btn"):
        st.session_state["show_dialog"] = True
        st.rerun()

# List incidents
incidents = list_incidents()
status_icons = {
    "open": "⚠️",
    "resolved": "✅",
}
if not incidents:
    st.info("No incidents reported yet.")
else:
    for incident in incidents:
        with st.expander(f"{status_icons.get(incident.status, incident.status)} {incident.name or 'No Name'}", expanded=False):
            st.write(f"**ID:** {incident.id}")
            st.write(f"**Description:** {incident.description}")
            if incident.solution:
                st.markdown("**Solution:**")
                st.write(incident.solution)
            # st.write(f"**Recipient email:** {incident.email}")
            # st.write(f"**Status:** {incident.status}")
            st.write(f"**SLA time (minutes):** {incident.sla_no_of_hours:.2f}")  # minutes for testing purposes
            st.write(f"**Notified:** {'Yes' if incident.notified else 'No'}")
            st.write(f"**Created at:** {incident.created_at}")
            st.write(f"**Updated at:** {incident.updated_at}")
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                if st.button("View", key=f"view_{incident.id}"):
                    st.session_state["selected_incident_id"] = incident.id
                    st.rerun()
            with col_b:
                if incident.status != "resolved":
                    solution_key = f"solution_input_{incident.id}"
                    if f"show_solution_{incident.id}" not in st.session_state:
                        st.session_state[f"show_solution_{incident.id}"] = False
                    if st.session_state[f"show_solution_{incident.id}"]:
                        solution = st.text_area("Enter solution:", key=solution_key)
                        submit_solution = st.button("Submit Solution", key=f"submit_solution_{incident.id}")
                        cancel_solution = st.button("Cancel", key=f"cancel_solution_{incident.id}")
                        if submit_solution:
                            if not solution.strip():
                                st.warning("Solution cannot be empty.")
                            else:
                                incident = resolve_incident(incident.id, solution)
                                add_resolved_incident_to_vectordb(
                                    # todo: get actual username
                                    username="admin",
                                    incident=incident
                                )
                                st.success("Incident resolved.")
                                st.session_state[f"show_solution_{incident.id}"] = False
                                st.rerun()
                        if cancel_solution:
                            st.session_state[f"show_solution_{incident.id}"] = False
                            st.rerun()
                    else:
                        if st.button("Mark as resolved", key=f"resolve_{incident.id}"):
                            st.session_state[f"show_solution_{incident.id}"] = True
                            st.rerun()
            with col_c:
                if st.button("Delete", key=f"delete_{incident.id}"):
                    delete_incident(incident.id)
                    delete_incident_from_vectordb(
                        # todo: get actual username
                        username="admin",
                        incident_id=incident.id
                    )
                    st.warning("Incident deleted.")
                    st.rerun()
            with col_d:
                if incident.status == "open":
                    if st.button("Ask AI assistant", key=f"ask_ai_{incident.id}"):
                        st.session_state["incident_prompt_request"] = incident.id
                        st.switch_page("pages/ai_assistant.py")

# Incident detail view
if st.session_state["selected_incident_id"]:
    incident = get_incident_by_id(st.session_state["selected_incident_id"])
    if incident:
        st.sidebar.header("Incident Details")
        st.sidebar.write(f"**ID:** {incident.id}")
        st.sidebar.write(f"**Name:** {incident.name}")
        st.sidebar.write(f"**Description:** {incident.description}")
        if incident.log:
            st.sidebar.markdown(f"**Log:**")
            st.sidebar.code(incident.log)
        else:
            st.sidebar.write("**Log:** N/A")
        if incident.solution:
            st.sidebar.markdown("**Solution:**")
            st.sidebar.write(incident.solution)
        st.sidebar.write(f"**Status:** {incident.status}")
        st.sidebar.write(f"**SLA time (minutes):** {incident.sla_no_of_hours:.2f}")  # minutes for testing purposes
        st.sidebar.write(f"**Recipient email:** {incident.email}")
        st.sidebar.write(f"**Notified:** {'Yes' if incident.notified else 'No'}")
        st.sidebar.write(f"**Created at:** {incident.created_at}")
        st.sidebar.write(f"**Updated at:** {incident.updated_at}")
        if incident.status != "resolved":
            sidebar_solution_key = f"sidebar_solution_input_{incident.id}"
            if f"sidebar_show_solution_{incident.id}" not in st.session_state:
                st.session_state[f"sidebar_show_solution_{incident.id}"] = False
            if st.session_state[f"sidebar_show_solution_{incident.id}"]:
                sidebar_solution = st.sidebar.text_area("Enter solution:", key=sidebar_solution_key)
                sidebar_submit_solution = st.sidebar.button("Submit Solution", key=f"sidebar_submit_solution_{incident.id}")
                sidebar_cancel_solution = st.sidebar.button("Cancel", key=f"sidebar_cancel_solution_{incident.id}")
                if sidebar_submit_solution:
                    if not sidebar_solution.strip():
                        st.sidebar.warning("Solution cannot be empty.")
                    else:
                        incident = resolve_incident(incident.id, sidebar_solution)
                        add_resolved_incident_to_vectordb(
                            # todo: get actual username
                            username="admin",
                            incident=incident,
                        )
                        st.sidebar.success("Incident resolved.")
                        st.session_state[f"sidebar_show_solution_{incident.id}"] = False
                        st.rerun()
                if sidebar_cancel_solution:
                    st.session_state[f"sidebar_show_solution_{incident.id}"] = False
                    st.rerun()
            else:
                if st.sidebar.button("Mark as resolved", key="sidebar_resolve"):
                    st.session_state[f"sidebar_show_solution_{incident.id}"] = True
                    st.rerun()
            if st.sidebar.button("Ask AI assistant", key=f"sidebar_ask_ai_{incident.id}"):
                st.session_state["incident_prompt_request"] = incident.id
                st.switch_page("pages/ai_assistant.py")
        if st.sidebar.button("Delete Incident", key="sidebar_delete"):
            delete_incident(incident.id)
            delete_incident_from_vectordb(
                # todo: get actual username
                username="admin",
                incident_id=incident.id
            )
            st.sidebar.warning("Incident deleted.")
            st.session_state["selected_incident_id"] = None
            st.rerun()
        if st.sidebar.button("Close Details", key="close_details"):
            st.session_state["selected_incident_id"] = None
            st.rerun()
    else:
        st.sidebar.error("Incident not found.")
        st.session_state["selected_incident_id"] = None
        st.rerun()

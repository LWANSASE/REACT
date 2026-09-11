import glob
import os
import re
import pandas as pd
import plotly.express as px
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="React Africa | Aspire Dashboard", layout="wide"
)

# --- CUSTOM CSS FOR METRIC TILES ---
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 12px;
    }
    .metric-title {
        color: #495057;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .metric-value {
        color: #1e293b;
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 4px;
        word-break: break-word;
    }
    .metric-sub {
        color: #059669;
        font-size: 12px;
        font-weight: 600;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- DATA AGGREGATION UTILITY ---
def process_and_aggregate_dataframe(df_raw):
    """Processes raw facility DataFrame and performs patient-level aggregation safely."""
    required_cols = ["FILE NUMBER"]
    for col in required_cols:
        if col not in df_raw.columns:
            st.error(f"Missing required column: `{col}` in uploaded file.")
            return None

    diag_col = (
        "DIAGNOSIS"
        if "DIAGNOSIS" in df_raw.columns
        else ("rdt_Diagnosis" if "rdt_Diagnosis" in df_raw.columns else None)
    )

    agg_dict = {}

    if "FACILITY" in df_raw.columns:
        agg_dict["FACILITY"] = ("FACILITY", "first")
    else:
        agg_dict["FACILITY"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "Uploaded Facility"
        )

    if "PATIENT GENDER" in df_raw.columns:
        agg_dict["PATIENT GENDER"] = ("PATIENT GENDER", "first")
    else:
        agg_dict["PATIENT GENDER"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "Unknown"
        )

    if "AGE" in df_raw.columns:
        agg_dict["AGE"] = ("AGE", "first")

    if "PATIENT HAS MALARIA" in df_raw.columns:
        agg_dict["PATIENT HAS MALARIA"] = ("PATIENT HAS MALARIA", "first")
    else:
        agg_dict["PATIENT HAS MALARIA"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "Unknown"
        )

    if "PATIENT HAS TUBERCULOSIS" in df_raw.columns:
        agg_dict["PATIENT HAS TUBERCULOSIS"] = (
            "PATIENT HAS TUBERCULOSIS",
            "first",
        )
    else:
        agg_dict["PATIENT HAS TUBERCULOSIS"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "Unknown"
        )

    if "PATIENT HIV STATUS" in df_raw.columns:
        agg_dict["PATIENT HIV STATUS"] = ("PATIENT HIV STATUS", "first")
    else:
        agg_dict["PATIENT HIV STATUS"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "Unknown"
        )

    if diag_col:
        agg_dict["DIAGNOSIS"] = (diag_col, "first")
    else:
        agg_dict["DIAGNOSIS"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "N/A"
        )

    if "NUMBER OF ANTIBIOTICS" in df_raw.columns:
        agg_dict["NUMBER OF ANTIBIOTICS"] = ("NUMBER OF ANTIBIOTICS", "first")
    else:
        agg_dict["NUMBER OF ANTIBIOTICS"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: 0
        )

    if "ANTIBIOTIC" in df_raw.columns:
        agg_dict["ANTIBIOTIC"] = (
            "ANTIBIOTIC",
            lambda x: [
                item
                for item in x.dropna().unique()
                if str(item).strip() != ""
            ],
        )
    else:
        agg_dict["ANTIBIOTIC"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: []
        )

    if "CULTURE SAMPLE" in df_raw.columns:
        agg_dict["CULTURE SAMPLE"] = (
            "CULTURE SAMPLE",
            lambda x: [
                item
                for item in x.dropna().unique()
                if str(item).strip() != ""
            ],
        )
    else:
        agg_dict["CULTURE SAMPLE"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: []
        )

    if "DEESCALATION CHANGE OF TREATMENT DONE" in df_raw.columns:
        agg_dict["DEESCALATION CHANGE OF TREATMENT DONE"] = (
            "DEESCALATION CHANGE OF TREATMENT DONE",
            "first",
        )
    else:
        agg_dict["DEESCALATION CHANGE OF TREATMENT DONE"] = pd.NamedAgg(
            column="FILE NUMBER", aggfunc=lambda x: "No"
        )

    if "TREATMENT TYPE" in df_raw.columns:
        agg_dict["TREATMENT TYPE"] = ("TREATMENT TYPE", "first")

    df_patients = df_raw.groupby("FILE NUMBER").agg(**agg_dict).reset_index()

    df_patients["ANTIBIOTIC_COUNT"] = df_patients["ANTIBIOTIC"].apply(len)
    df_patients["CULTURE_COUNT"] = df_patients["CULTURE SAMPLE"].apply(len)

    return df_patients


# --- AUTOMATIC FILE DISCOVERY FUNCTION ---
@st.cache_data(show_spinner=False)
def auto_load_facility_files(data_folder=r"cdata"):
    """
    Scans specified folder (or working directory) for CSV files matching facility patterns.
    Matches filenames containing: Nakuru, Levy, AAR, UTH (case-insensitive).
    """
    facility_data = {}
    search_paths = []

    if os.path.exists(data_folder):
        search_paths.append(os.path.join(data_folder, "*.csv"))
        search_paths.append(os.path.join(data_folder, "*.xlsx"))

    search_paths.append("*.csv")
    search_paths.append("*.xlsx")

    found_files = []
    for path in search_paths:
        found_files.extend(glob.glob(path))

    patterns = {
        "Nakuru": ["nakuru"],
        "Levy": ["levy"],
        "AAR": ["aar"],
        "UTH": ["uth"],
    }

    for key, keywords in patterns.items():
        matched_file = None
        for filepath in found_files:
            filename = os.path.basename(filepath).lower()
            if any(kw in filename for kw in keywords):
                matched_file = filepath
                break

        if matched_file:
            try:
                if matched_file.endswith(".csv"):
                    raw_df = pd.read_csv(matched_file)
                else:
                    raw_df = pd.read_excel(matched_file)

                aggregated_df = process_and_aggregate_dataframe(raw_df)
                facility_data[key] = {
                    "raw_df": raw_df,
                    "pts_df": aggregated_df,
                    "file_path": matched_file,
                }
            except Exception as e:
                st.warning(f"Failed to load {matched_file}: {e}")

    return facility_data


# --- HEADER SECTION ---
st.title("💊 REACT AFRICA | ASPIRE DASHBOARD")
st.markdown(
    "Data auto-imported from directory and consolidated by **`FILE NUMBER`** (1 Patient = 1 Record)."
)

# Auto-scan local files on startup
loaded_facility_files = auto_load_facility_files()

tab_nakuru, tab_levy, tab_aar, tab_uth = st.tabs([
    "🇰🇪 Nakuru (Kenya)",
    "🇿🇲 Levy (Zambia)",
    "🇰🇪 AAR  (Kenya)",
    "🇿🇲 UTH (Zambia)",
])

facilities_map = {
    "Nakuru": (
        "Nakuru Level 5 Hospital",
        "Kenya",
        "Nakuru County Referral Hospital",
        tab_nakuru,
    ),
    "Levy": (
        "Levy Mwanawasa General Hospital",
        "Zambia",
        "Levy Mwanawasa Hospital",
        tab_levy,
    ),
    "AAR": ("AAR Hospital", "Kenya", "AAR Hospital", tab_aar),
    "UTH": (
        "University Teaching Hospital",
        "Zambia",
        "University Teaching Hospital (Paediatric)",
        tab_uth,
    ),
}


def render_tile(title, value, subtext=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_facility_dashboard(
    facility_code, full_name, country, facility_match, tab
):
    with tab:
        pts = pd.DataFrame()
        raw_fac_df = pd.DataFrame()
        loaded_filename = None

        # Check if auto-loaded dataset exists for this facility key
        if facility_code in loaded_facility_files:
            fac_info = loaded_facility_files[facility_code]
            raw_fac_df = fac_info["raw_df"]
            pts = fac_info["pts_df"]
            loaded_filename = fac_info["file_path"]

        # Manual File Uploader (Optional Override)
        with st.expander("📁 Optional Manual Data Override / File Source"):
            uploaded_file = st.file_uploader(
                f"Override automatically detected CSV/Excel dataset for **{full_name}**",
                type=["csv", "xlsx", "xls"],
                key=f"uploader_{facility_code}",
            )
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        raw_fac_df = pd.read_csv(uploaded_file)
                    else:
                        raw_fac_df = pd.read_excel(uploaded_file)
                    pts = process_and_aggregate_dataframe(raw_fac_df)
                    loaded_filename = uploaded_file.name
                    st.success(
                        f"Manually loaded `{uploaded_file.name}` for **{full_name}**."
                    )
                except Exception as e:
                    st.error(f"Error reading file: {e}")
                    return

        if loaded_filename:
            st.caption(f"📄 Active Data Source File: `{loaded_filename}`")
        else:
            st.warning(
                f"⚠️ No CSV file matching pattern `*{facility_code.lower()}*.csv` was automatically found."
            )

        # --- DYNAMIC HEADER EXTRACTION FROM CSV ---
        if not raw_fac_df.empty and "FACILITY" in raw_fac_df.columns:
            display_facility = (
                raw_fac_df["FACILITY"].dropna().iloc[0]
                if not raw_fac_df["FACILITY"].dropna().empty
                else full_name
            )
        else:
            display_facility = full_name

        if not raw_fac_df.empty and "COUNTRY" in raw_fac_df.columns:
            display_country = (
                raw_fac_df["COUNTRY"].dropna().iloc[0]
                if not raw_fac_df["COUNTRY"].dropna().empty
                else country
            )
        else:
            display_country = country

        phase_col = next(
            (
                c
                for c in ["PHASE", "PROJECT_PHASE", "PROJECT PHASE"]
                if c in raw_fac_df.columns
            ),
            None,
        )
        if not raw_fac_df.empty and phase_col:
            display_phase = (
                raw_fac_df[phase_col].dropna().iloc[0]
                if not raw_fac_df[phase_col].dropna().empty
                else "ENDLINE 2026"
            )
        else:
            display_phase = "ENDLINE 2026"

        # --- HEADER DISPLAY CARDS ---
        b1, b2, b3 = st.columns(3)
        with b1:
            st.info(f"**🏥 Facility:** {display_facility}")
        with b2:
            st.warning(f"**🌍 Country:** {display_country}")
        with b3:
            st.success(f"**📌 Phase:** {display_phase}")

        total_patients = len(pts) if pts is not None else 0

        if total_patients == 0:
            st.error(
                f"No records could be loaded for **{full_name}**. Ensure a file named like `KE_{facility_code}.csv` or `{facility_code}.csv` exists in the project or `cdata/` directory."
            )
            return

        # --- KEY PERFORMANCE INDICATORS ---
        st.header("📊 Key Performance Indicators (Patient Base)")

        r1_c1, r1_c2, r1_c3 = st.columns(3)
        with r1_c1:
            render_tile(
                "Total Patients (Files)",
                f"{total_patients:,}",
                "Unique FILE NUMBER Records",
            )

        with r1_c2:
            gender_counts = pts["PATIENT GENDER"].value_counts()
            gender_str = " • ".join([
                f"{k}: {v} ({(v/total_patients)*100:.1f}%)"
                for k, v in gender_counts.items()
            ])
            render_tile(
                "Gender Breakdown",
                f"{len(pts['PATIENT GENDER'].dropna()):,}",
                gender_str,
            )

        with r1_c3:
            total_abx_courses = pts["ANTIBIOTIC_COUNT"].sum()
            render_tile(
                "Total Antibiotics Prescribed",
                f"{total_abx_courses:,}",
                "",
            )

        r2_c1, r2_c2, r2_c3 = st.columns(3)
        with r2_c1:
            pts_3plus = (pts["ANTIBIOTIC_COUNT"] >= 3).sum()
            pct_3plus = (pts_3plus / total_patients) * 100
            render_tile(
                "Patients on ≥3 Antibiotics",
                f"{pts_3plus:,}",
                f"{pct_3plus:.1f}% of patients",
            )

        with r2_c2:
            surgical_mask = (
                pts["DIAGNOSIS"]
                .astype(str)
                .str.contains("Surgical", case=False, na=False)
            )
            surgical_count = surgical_mask.sum()
            effective_denominator = total_patients - surgical_count

            pts_with_cultures = (pts["CULTURE_COUNT"] > 0).sum()
            total_cultures = pts["CULTURE_COUNT"].sum()

            pct_cultures = (
                (pts_with_cultures / effective_denominator * 100)
                if effective_denominator > 0
                else 0.0
            )

            render_tile(
                "Patients with Cultures",
                f"{pts_with_cultures:,}",
                f"{total_cultures} Total Samples ({pct_cultures:.1f}%)",
            )

        with r2_c3:
            deescalated = (
                pts["DEESCALATION CHANGE OF TREATMENT DONE"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["yes", "1", "true"])
                .sum()
            )
            pct_deesc = (deescalated / total_patients) * 100
            render_tile(
                "De-escalated Cases",
                f"{deescalated:,}",
                f"{pct_deesc:.1f}% compliance Patients",
            )

        # --- SECOND TILE ROW: COMMON METRICS ---
        all_abx = [abx for sublist in pts["ANTIBIOTIC"] for abx in sublist]
        all_cultures = [c for sublist in pts["CULTURE SAMPLE"] for c in sublist]

        r3_c1, r3_c2, r3_c3 = st.columns(3)

        with r3_c1:
            if all_abx:
                top_abx_series = pd.Series(all_abx).value_counts()
                top_abx_name = top_abx_series.index[0]
                top_abx_count = top_abx_series.iloc[0]
                pct_abx = (top_abx_count / len(all_abx)) * 100
                render_tile(
                    "Most Common Antibiotic",
                    str(top_abx_name),
                    f"{top_abx_count:,} Prescriptions ({pct_abx:.1f}%)",
                )
            else:
                render_tile(
                    "Most Common Antibiotic", "N/A", "No Data Available"
                )

        with r3_c2:
            if all_cultures:
                top_spec_series = pd.Series(all_cultures).value_counts()
                top_spec_name = top_spec_series.index[0]
                top_spec_count = top_spec_series.iloc[0]
                pct_spec = (top_spec_count / len(all_cultures)) * 100
                render_tile(
                    "Most Common Specimen",
                    str(top_spec_name),
                    f"{top_spec_count:,} Samples ({pct_spec:.1f}%)",
                )
            else:
                render_tile("Most Common Specimen", "N/A", "No Data Available")

        with r3_c3:
            diag_series = pts["DIAGNOSIS"].dropna()
            diag_series = diag_series[
                diag_series.astype(str).str.strip() != "N/A"
            ]
            if not diag_series.empty:
                top_diag_counts = diag_series.value_counts()
                top_diag_name = top_diag_counts.index[0]
                top_diag_count = top_diag_counts.iloc[0]
                pct_diag = (top_diag_count / total_patients) * 100
                render_tile(
                    "Most Common Diagnosis",
                    str(top_diag_name),
                    f"{top_diag_count:,} Patients ({pct_diag:.1f}%)",
                )
            else:
                render_tile(
                    "Most Common Diagnosis", "N/A", "No Data Available"
                )

        st.markdown("---")

        # --- GUIDELINES COMPLIANCE SECTION ---
        st.header(
            "📜 Guidelines Compliance Analysis (Per Antibiotic Prescribed)"
        )

        target_comp_col = next(
            (
                c
                for c in [
                    "GUIDELINES COMPLIANCE",
                    "GUIDELINE COMPLIANCE",
                    "COMPLIANCE STATUS",
                    "COMPLIANCE",
                ]
                if c in raw_fac_df.columns
            ),
            None,
        )

        if target_comp_col:
            comp_series = (
                raw_fac_df[target_comp_col]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            # 1. Total Prescribed Antibiotics across the facility (Denominator)
            total_prescriptions = len(all_abx) if all_abx else len(comp_series.dropna())

            # 2. Compliant Count (Yes)
            compliant_count = comp_series.isin(["YES", "Y", "1", "TRUE"]).sum()

            # 3. Non-Compliant Count (Derived strictly so Compliant + Non-Compliant = Total)
            non_compliant_count = max(0, total_prescriptions - compliant_count)

            # 4. Reconciled Percentages (Must sum to 100.0%)
            if total_prescriptions > 0:
                compliant_pct = (compliant_count / total_prescriptions) * 100
                non_compliant_pct = 100.0 - compliant_pct
            else:
                compliant_pct = 0.0
                non_compliant_pct = 0.0

            gc1, gc2, gc3 = st.columns(3)
            with gc1:
                render_tile(
                    "Guidelines Compliance",
                    f"{total_prescriptions:,}",
                    f"from {total_patients:,} reviewed files",
                )
            with gc2:
                render_tile(
                    "Compliant Prescriptions (Yes)",
                    f"{compliant_count:,}",
                    f"{compliant_pct:.1f}% Total Prescriptions",
                )
            with gc3:
                render_tile(
                    "Non-Compliant Prescriptions (No)",
                    f"{non_compliant_count:,}",
                    f"{non_compliant_pct:.1f}% Total Prescriptions",
                )
        else:
            st.error(
                "Missing required column **`GUIDELINES COMPLIANCE`** in dataset."
            )

        st.markdown("---")

        # --- TOP 5 ANTIBIOTICS & TREATMENT TYPE SECTION ---
        st.header(
            "🎯 Stewardship Priorities: Top 5 Antibiotics & Treatment Type"
        )
        sec1_c1, sec1_c2 = st.columns(2)

        with sec1_c1:
            st.subheader("🥇 Top 5 Most Prescribed Antibiotics")
            if all_abx:
                top5_abx = (
                    pd.Series(all_abx).value_counts().head(5).reset_index()
                )
                top5_abx.columns = ["Antibiotic", "Prescription Count"]
                top5_abx["Percentage"] = (
                    top5_abx["Prescription Count"] / len(all_abx) * 100
                ).round(1)

                fig_top5 = px.bar(
                    top5_abx,
                    x="Prescription Count",
                    y="Antibiotic",
                    orientation="h",
                    title="Top 5 Antibiotics by Total Prescriptions",
                    text=top5_abx.apply(
                        lambda r: (
                            f"{int(r['Prescription Count']):,}"
                            f" ({r['Percentage']}%)"
                        ),
                        axis=1,
                    ),
                    color="Prescription Count",
                    color_continuous_scale="Viridis",
                )
                fig_top5.update_layout(
                    yaxis={"categoryorder": "total ascending"}
                )
                fig_top5.update_traces(textangle=0, textposition="outside")
                fig_top5.update_xaxes(tickangle=0)
                fig_top5.update_yaxes(tickangle=0)
                st.plotly_chart(
                    fig_top5,
                    use_container_width=True,
                    key=f"top5_abx_chart_{facility_code}",
                )
            else:
                st.info("No antibiotic data available to derive Top 5.")

        with sec1_c2:
            st.subheader("💉 Treatment Type Breakdown")
            if "TREATMENT TYPE" in raw_fac_df.columns:
                tx_series = (
                    raw_fac_df["TREATMENT TYPE"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )
                if not tx_series.empty:
                    tx_df = tx_series.value_counts().reset_index()
                    tx_df.columns = ["TREATMENT TYPE", "Count"]

                    fig_tx = px.pie(
                        tx_df,
                        values="Count",
                        names="TREATMENT TYPE",
                        title="Treatment Type Breakdown",
                        hole=0.4,
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig_tx.update_traces(textinfo="label+percent+value")
                    st.plotly_chart(
                        fig_tx,
                        use_container_width=True,
                        key=f"tx_type_chart_{facility_code}",
                    )
                else:
                    st.warning(
                        "Column **`TREATMENT TYPE`** is present but contains"
                        " no data."
                    )
            else:
                st.error(
                    "Missing required column **`TREATMENT TYPE`** in the"
                    " dataset."
                )

        st.markdown("---")

        # --- SYNDROME VS. ANTIBIOTICS MATRIX TABLE ---
        st.header(
            "📋 Antibiotic Usage Matrix across Top 5 Syndromes / Diagnoses"
        )
        st.markdown(
            "Frequency of top prescribed antibiotics distributed across the"
            " **Top 5 Syndromes (Diagnoses)**."
        )

        valid_pts = pts.dropna(subset=["DIAGNOSIS"]).copy()
        valid_pts = valid_pts[
            valid_pts["DIAGNOSIS"].astype(str).str.strip().str.upper() != "N/A"
        ]

        if not valid_pts.empty and all_abx:
            top5_syndromes = (
                valid_pts["DIAGNOSIS"].value_counts().head(5).index.tolist()
            )
            top10_abx_list = (
                pd.Series(all_abx).value_counts().head(10).index.tolist()
            )

            exploded_pts = valid_pts[
                ["FILE NUMBER", "DIAGNOSIS", "ANTIBIOTIC"]
            ].explode("ANTIBIOTIC")
            exploded_pts["ANTIBIOTIC"] = (
                exploded_pts["ANTIBIOTIC"].astype(str).str.strip()
            )

            exploded_pts = exploded_pts[
                (exploded_pts["DIAGNOSIS"].isin(top5_syndromes))
                & (exploded_pts["ANTIBIOTIC"].isin(top10_abx_list))
                & (exploded_pts["ANTIBIOTIC"] != "")
            ]

            if not exploded_pts.empty:
                matrix_df = (
                    exploded_pts.groupby(["ANTIBIOTIC", "DIAGNOSIS"])
                    .size()
                    .unstack(fill_value=0)
                )

                matrix_df = (
                    matrix_df.reindex(
                        index=top10_abx_list,
                        columns=top5_syndromes,
                        fill_value=0,
                    )
                    .dropna(how="all")
                )

                matrix_df["Total Prescriptions"] = matrix_df.sum(axis=1)

                st.dataframe(
                    matrix_df.style.background_gradient(
                        cmap="YlGnBu", subset=matrix_df.columns[:-1]
                    ).format("{:,}"),
                    use_container_width=True,
                )
            else:
                st.info(
                    "No matching antibiotic prescriptions found for the top 5"
                    " diagnoses."
                )
        else:
            st.info(
                "Insufficient diagnosis or antibiotic data available to generate"
                " matrix."
            )

        st.markdown("---")

        # --- VISUAL ANALYTICS ---
        st.header("📈 Visual Analytics (Patient-Level)")

        c1, c2 = st.columns(2)
        with c1:
            if all_abx:
                t10_abx = (
                    pd.Series(all_abx).value_counts().head(10).reset_index()
                )
                t10_abx.columns = ["Antibiotic", "Patients"]
                fig = px.bar(
                    t10_abx,
                    x="Patients",
                    y="Antibiotic",
                    orientation="h",
                    title="Top 10 Antibiotics Prescribed (Patient Count)",
                    text="Patients",
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                fig.update_traces(textangle=0, textposition="outside")
                fig.update_xaxes(tickangle=0)
                fig.update_yaxes(tickangle=0)
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"top_abx_{facility_code}",
                )

        with c2:
            abx_dist = pts["ANTIBIOTIC_COUNT"].value_counts().reset_index()
            abx_dist.columns = ["Antibiotics Per Patient", "Patients"]
            fig = px.pie(
                abx_dist,
                values="Patients",
                names="Antibiotics Per Patient",
                title="Patient Distribution by Antibiotic Count",
                hole=0.4,
            )
            fig.update_traces(textinfo="value+percent")
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"abx_dist_{facility_code}",
            )

        c3, c4 = st.columns(2)
        with c3:
            if not pts["DIAGNOSIS"].dropna().empty:
                t_diag = pts["DIAGNOSIS"].value_counts().head(10).reset_index()
                t_diag.columns = ["Diagnosis", "Patients"]
                fig = px.bar(
                    t_diag,
                    x="Diagnosis",
                    y="Patients",
                    title="Top 10 Diagnoses (1 Per Patient)",
                    text="Patients",
                    color="Patients",
                )
                fig.update_traces(textangle=0, textposition="outside")
                fig.update_xaxes(tickangle=0)
                fig.update_yaxes(tickangle=0)
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"top_diag_{facility_code}",
                )

        with c4:
            if all_cultures:
                spec_counts = (
                    pd.Series(all_cultures).value_counts().reset_index()
                )
                spec_counts.columns = ["Specimen Type", "Count"]
                fig = px.bar(
                    spec_counts,
                    x="Specimen Type",
                    y="Count",
                    title="Culture Specimens Taken Across Patients",
                    text="Count",
                )
                fig.update_traces(textangle=0, textposition="outside")
                fig.update_xaxes(tickangle=0)
                fig.update_yaxes(tickangle=0)
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"specimen_{facility_code}",
                )

        st.markdown("---")

        # --- CO-MORBIDITIES SECTION ---
        st.header("🦠 Option Data & Co-morbidities Breakdown")
        col_tb, col_malaria, col_hiv = st.columns(3)

        with col_tb:
            tb_counts = (
                pts["PATIENT HAS TUBERCULOSIS"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .str.capitalize()
                .value_counts()
                .reset_index()
            )
            tb_counts.columns = ["Status", "Patients"]
            fig_tb = px.bar(
                tb_counts,
                x="Status",
                y="Patients",
                title="TB Status Breakdown",
                text="Patients",
                color="Status",
                color_discrete_map={
                    "Yes": "#dc2626",
                    "No": "#2563eb",
                    "Unknown": "#6b7280",
                },
            )
            fig_tb.update_traces(textangle=0, textposition="outside")
            fig_tb.update_xaxes(tickangle=0)
            fig_tb.update_yaxes(tickangle=0)
            st.plotly_chart(
                fig_tb,
                use_container_width=True,
                key=f"tb_chart_{facility_code}",
            )

        with col_malaria:
            mal_counts = (
                pts["PATIENT HAS MALARIA"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .str.capitalize()
                .value_counts()
                .reset_index()
            )
            mal_counts.columns = ["Status", "Patients"]
            fig_malaria = px.bar(
                mal_counts,
                x="Status",
                y="Patients",
                title="Malaria Status Breakdown",
                text="Patients",
                color="Status",
                color_discrete_map={
                    "Yes": "#d97706",
                    "No": "#2563eb",
                    "Unknown": "#6b7280",
                },
            )
            fig_malaria.update_traces(textangle=0, textposition="outside")
            fig_malaria.update_xaxes(tickangle=0)
            fig_malaria.update_yaxes(tickangle=0)
            st.plotly_chart(
                fig_malaria,
                use_container_width=True,
                key=f"malaria_chart_{facility_code}",
            )

        with col_hiv:
            hiv_counts = (
                pts["PATIENT HIV STATUS"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .str.capitalize()
                .value_counts()
                .reset_index()
            )
            hiv_counts.columns = ["Status", "Patients"]
            fig_hiv = px.bar(
                hiv_counts,
                x="Status",
                y="Patients",
                title="HIV Status Breakdown",
                text="Patients",
                color="Status",
                color_discrete_map={
                    "Positive": "#ef4444",
                    "Negative": "#10b981",
                    "Unknown": "#6b7280",
                    "None": "#6b7280",
                },
            )
            fig_hiv.update_traces(textangle=0, textposition="outside")
            fig_hiv.update_xaxes(tickangle=0)
            fig_hiv.update_yaxes(tickangle=0)
            st.plotly_chart(
                fig_hiv,
                use_container_width=True,
                key=f"hiv_chart_{facility_code}",
            )


# Render facility tabs
for code, (name, country, match_str, tab_obj) in facilities_map.items():
    render_facility_dashboard(code, name, country, match_str, tab_obj)

import re
import streamlit as st
import pandas as pd
from io import BytesIO

# m/z values within this many units are treated as the same compound when
# comparing peak labels (distinct compounds are typically much further apart
# than the noise between repeated measurements of the same one).
MASS_MATCH_TOLERANCE = 0.3

MZ_PATTERN = re.compile(r"m/z\s*([\d.]+)", re.IGNORECASE)


def parse_mass(label):
    """Return the m/z value in a Peak Label like 'm/z 351.30', or None if it isn't one."""
    if label is None:
        return None
    match = MZ_PATTERN.search(str(label))
    return float(match.group(1)) if match else None


def cluster_within_tolerance(values, tol):
    """Group sorted numeric values into clusters where neighbours are within tol of each other."""
    values = sorted(values)
    clusters = []
    current = []
    for v in values:
        if current and v - current[-1] > tol:
            clusters.append(current)
            current = []
        current.append(v)
    if current:
        clusters.append(current)
    return clusters


def summarize_labels(labels, tol=MASS_MATCH_TOLERANCE):
    """Reduce the Peak Labels seen for one RT (across all samples, blanks excluded) to a
    single display label, plus a warning string if the labels didn't agree."""
    masses, texts = [], []
    for label in labels:
        mass = parse_mass(label)
        if mass is not None:
            masses.append(mass)
        else:
            text = str(label).strip()
            if text:
                texts.append(text)

    if masses:
        clusters = sorted(cluster_within_tolerance(masses, tol), key=len, reverse=True)
        best_mass = sum(clusters[0]) / len(clusters[0])
        display_label = f"m/z {best_mass:.2f}"
        if len(clusters) == 1:
            return display_label, None
        other_masses = ", ".join(f"{sum(c) / len(c):.2f}" for c in clusters[1:])
        return display_label, f"conflicting m/z values ({best_mass:.2f} vs {other_masses}) - showing the most common"

    if texts:
        distinct = list(dict.fromkeys(texts))  # unique, preserving order
        if len(distinct) == 1:
            return distinct[0], None
        return " + ".join(distinct), f"labels disagree ({', '.join(distinct)}) - showing combined label"

    return "", None


def with_label_header(display_df, label_map):
    """Return a copy of display_df with a second column-header row showing each RT's label."""
    if not label_map:
        return display_df

    def label_for(col):
        try:
            rt = float(str(col).split("RT ")[-1])
        except ValueError:
            return ""
        return label_map.get(rt, "")

    out = display_df.copy()
    out.columns = pd.MultiIndex.from_tuples(
        [(col, label_for(col)) for col in out.columns],
        names=["RT", "Label"]
    )
    return out

# Logo on top left
st.image('./catsci-logo.svg', width=200)  # Adjust width as needed

# Name of the script
st.title('SCR-01: LC area txt to xslx 🔁')  # Replace with your script name

# Brief description
st.markdown('''
    This app helps to post-process the *txt* file exported by the `exportPeaks.qs` script for Mnova. 
    It outputs a table of peak areas or LCAP values that can be easily copied into Excel.
    ''')

# Spacer after table
st.markdown('''
    ''')

# Quick instruction
with st.expander("Instructions📝"):
    st.markdown('''
        1. Download all of your *.mnova* files from Signals/LOGS to one folder.
        2. Open MestReNova
            - Select the *"Tools"* tab
            - *Import* -> "Multi-Open Wildcard..."
            - In the new window that opens, select the folder where you saved all files and put `*.mnova` in the empty box.
            - Tick "Open Mnova Files into a Single Document"
            - Wait ⌛
        3. You can edit the integrations or keep them as they are. Click the folder icon "Run Script" in the same *"Tools"* tab.
        4. Find and open the saved script `exportPeaks.qs`
        5. Save *txt file*.
        6. Upload this *txt file* to this app as it is and enjoy your Excel table😊\\
        **Creation of SP3 table**
        1. You can create an SP3 table based on the previous output. To do so, you need to define the start and end RT that you would like to include.
        2. Use the slider to define the range, the border value will be included.
        3. Define the reference peak from the list.
        4. Push the button, enjoy your SP3 table.
    ''')

# Quick explanation
with st.expander("How does it work❓"):
    st.markdown('''
        In case the output data isn't consistent, there is processing pipeline.
        1. File is uploaded to app and converted to DataFrame.
        2. It parses "Sample Name", "RT (mins)", "Area" and (if present) "Peak Label" columns, and ignores the file's own "LCAP (%)" column.
        LCAP is always calculated by this app from the Area values, not read from the file.
        3. "RT (mins)" are rounded to the second decimal places (e.g. 1.23).
        4. The table is transposed and grouped by "Sample" index and "RTs" columns. If two peaks in the same sample round to the
        same RT, their areas are summed and you'll see a warning listing the affected samples.
        5. All absent data is filled by zeros. It happens when a peak is absent in one sample but present in another.
        6. Hard part: To solve the problem of peak drift between samples. The app compares neighbouring "RTs" (sorted) and if the
        difference is ≤ the threshold you set, the columns are merged, chaining together runs of drifting peaks (e.g. 3.20, 3.21, 3.22).
        The final RT is the highest in the group. Merging only happens where at least one value in each row across the pair being
        compared is 0, so two genuinely co-occurring peaks won't be merged into one. If "Peak Label" values look like m/z (e.g.
        "m/z 351.30") for both RTs, they must also agree (within 0.3) or the peaks won't be merged, since it's then unclear
        which mass to keep.
        7. It then drops the excess columns that are no longer needed after the merge.
        8. If a "Peak Label" column was present, each RT column gets a label underneath it: the most common m/z value seen for
        that RT, or - if the labels are text descriptors rather than masses - the descriptor if all samples agree, otherwise
        the distinct descriptors joined with "+" (e.g. "SM + solvent"). Either way, any disagreement is flagged in a warning
        below the table.
        9. And finally it exports the DataFrame (which is shown on the screen) to Excel that you can download 🔚\\
        **Creation of SP3 table**
        1. Then the app takes the index row of table and converts it to a list.
        2. After that it creates a slider based on this list.
        3. Additional selection of reference peak is depends on the list from step 1. Then it takes input value.
        4. Range and refernce values are saved to the variable and taken into account after pressing button. The reference peak
        must fall inside the selected range, and the button only appears once it does.
        5. During processing script deletes excess columns (keeping only the same peaks included in the table above) amd then
        recalculates LCAP based on it's total sum of row.
        6. Then simple data export to show and download table.
    ''')

uploaded_file = st.file_uploader("Upload your *.txt* file")

# File uploader

# Function to convert DataFrame to Excel file in memory
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    output_df = df.copy()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        output_df.to_excel(writer, index=True)
        writer.book.close()  # Save the workbook
    return output.getvalue()  # Get the binary content


if uploaded_file is not None:
    # Read the uploaded file
    try:
        df = pd.read_csv(uploaded_file, sep='\t', engine='python')
    except Exception as e:
        st.error(f"Could not read the uploaded file: {e}")
        st.stop()

    required_columns = {'Sample Name', 'RT (mins)', 'Area'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        st.error(
            f"The uploaded file is missing required column(s): {', '.join(sorted(missing_columns))}. "
            "Please upload the txt file exported by exportPeaks.qs without modification."
        )
        st.stop()

    # Rounding the 'RT (mins)' column to the nearest hundredth
    df['RT (mins)'] = df['RT (mins)'].round(2)

    # Collect the Peak Label seen for each RT bucket, across all samples, for use below
    # (as a header row and as a check before merging drifting peaks). Optional column.
    has_labels = 'Peak Label' in df.columns
    labels_by_rt = {}
    if has_labels:
        for rt, group in df.groupby('RT (mins)')['Peak Label']:
            labels_by_rt[rt] = [l for l in group if pd.notna(l) and str(l).strip() != '']

    # Warn if multiple peaks in the same sample round to the same RT - their areas will be summed
    dup_mask = df.duplicated(subset=['Sample Name', 'RT (mins)'], keep=False)
    if dup_mask.any():
        dup_pairs = (
            df.loc[dup_mask, ['Sample Name', 'RT (mins)']]
            .drop_duplicates()
            .sort_values(['Sample Name', 'RT (mins)'])
        )
        dup_list = "\n".join(f"- {row['Sample Name']}: RT {row['RT (mins)']:.2f}" for _, row in dup_pairs.iterrows())
        st.warning(
            "Some samples have multiple peaks that round to the same RT (mins) value. "
            "Their areas have been summed together for that RT:\n\n" + dup_list
        )

    # Pivoting the DataFrame
    # Each unique rounded 'RT (mins)' value becomes a column. Peaks that round to the
    # same RT within a sample (see warning above, if any) are summed rather than averaged.
    pivot_df = df.pivot_table(index='Sample Name',
                        columns='RT (mins)',
                        values="Area",
                        aggfunc='sum')

    #Filling NaN values with zero
    pivot_df.fillna(0, inplace=True)

    df=pivot_df
    merged_df = pd.DataFrame(index=df.index)
    columns_to_drop = set()  # Store columns that should be dropped after merging
    source_rts_by_final_col = {}  # Maps each final RT column back to the pre-merge RT(s) it came from

    do_merge = st.toggle("Merge peaks with similar RTs (to account for RT drift across samples)")

    if do_merge:

        threshold = st.number_input("Set the threshold for merging peaks (in minutes)", min_value=0.001, max_value=0.100, value=0.020, step=0.001, format="%0.3f")

        # Sort RTs and only compare neighbours, unioning runs of drifting peaks together
        # (e.g. 3.20, 3.21, 3.22 all merge into one column) rather than only merging pairs.
        sorted_rts = sorted(df.columns, key=float)
        parent = list(range(len(sorted_rts)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(len(sorted_rts) - 1):
            rt1, rt2 = sorted_rts[i], sorted_rts[i + 1]
            # Check the difference between neighbouring RTs is within the specified range
            if abs(float(rt1) - float(rt2)) <= threshold:
                # If both RTs have a known mass, don't merge them unless the masses agree -
                # a close RT with a clearly different mass is a different compound.
                masses1 = [m for m in (parse_mass(l) for l in labels_by_rt.get(rt1, [])) if m is not None]
                masses2 = [m for m in (parse_mass(l) for l in labels_by_rt.get(rt2, [])) if m is not None]
                if masses1 and masses2 and not any(abs(m1 - m2) <= MASS_MATCH_TOLERANCE for m1 in masses1 for m2 in masses2):
                    continue
                # Check if at least one value in each row across these columns is 0
                condition = (df[rt1] == 0.0) | (df[rt2] == 0.0)
                if condition.any():  # If the condition is true for any row
                    union(i, i + 1)

        groups = {}
        for i, rt in enumerate(sorted_rts):
            groups.setdefault(find(i), []).append(rt)

        for cols in groups.values():
            final_col = max(cols, key=lambda x: float(x)) if len(cols) > 1 else cols[0]
            source_rts_by_final_col[final_col] = cols
            if len(cols) > 1:
                # Sum the columns and use the highest RT value in the group as the column name
                merged_df[final_col] = df[cols].sum(axis=1)
                columns_to_drop.update(cols)

        # Drop the processed columns from df
        df.drop(columns=list(columns_to_drop), inplace=True)

    # Add the remaining columns that were not merged to merged_df
    for col in df.columns:
        if col not in merged_df:
            merged_df[col] = df[col]
        source_rts_by_final_col.setdefault(col, [col])

    # Sort the columns as they might be out of order after merging
    merged_df = merged_df.sort_index(axis=1)
    merged_df = merged_df.round(2)

    # Reduce each final column's source Peak Labels to a single display label, flagging
    # any RT where the labels didn't agree.
    label_map = {}
    label_warnings = []
    if has_labels:
        for col in merged_df.columns:
            labels = [l for rt in source_rts_by_final_col.get(col, [col]) for l in labels_by_rt.get(rt, [])]
            display_label, warning = summarize_labels(labels)
            if display_label:
                label_map[col] = display_label
            if warning:
                label_warnings.append(f"RT {col:.2f}: {warning}")

    merged_df_display = merged_df.copy()
    merged_df_display.columns = [f"RT {col:.2f}" for col in merged_df_display.columns]

    calculate_lcap = st.toggle("Calculate LCAP (Relative Peak Area) from the merged data")

    if not calculate_lcap:
        st.dataframe(with_label_header(merged_df_display, label_map))
        final_df = merged_df_display
    else:
        # Identify retention time columns
        numeric_cols = merged_df_display.select_dtypes(include='number').columns.tolist() # find numeric columns and convert to list
        peak_area_data = merged_df_display[numeric_cols] # splits into just numeric values

        # Creates a single-row DataFrame of checkboxes (True by default)
        col_selector_df = pd.DataFrame([True] * len(numeric_cols), index=numeric_cols).T
        col_selector_df.index = ["Include"]

        def checkbox_label(col):
            try:
                rt = float(col.split("RT ")[-1])
            except ValueError:
                return col
            label = label_map.get(rt)
            return f"{col} ({label})" if label else col

        st.write("Select Retention Times to Include in LCAP:")
        edited_selector = st.data_editor(
            col_selector_df,
            use_container_width=True,
            column_config={col: st.column_config.CheckboxColumn(label=checkbox_label(col), required=True) for col in numeric_cols}
        )

        # Get selected columns from checkbox row
        selected_cols = [col for col in numeric_cols if edited_selector.iloc[0][col]]

        if not selected_cols:
            st.warning("Please select at least one retention time to calculate LCAP.")

        # Calculates LCAP from selected peaks
        selected_data = peak_area_data[selected_cols]
        total_areas = selected_data.sum(axis=1)
        lcap_data = selected_data.div(total_areas, axis=0) * 100

        lcap_results = lcap_data.round(2)
        final_df = lcap_results
        st.dataframe(with_label_header(final_df, label_map))

    if label_warnings:
        st.warning("Peak label conflicts detected:\n\n" + "\n".join(f"- {w}" for w in label_warnings))

    # Download intermediate table
    st.download_button(
        label="Download full table",
        data=convert_df_to_excel(with_label_header(final_df, label_map)),
        file_name="Area_RT.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown('''
    Now we can create SP3 table with LCAP and RRT
    ''')
    st.latex(r'''
    LCAP=\frac{A_{i}}{ \sum A }\qquad RRT= \frac{RT_{analyte}}{RT_{reference}}
    ''')

    final_df.columns = [float(col.split("RT ")[-1]) for col in final_df.columns]
    
    start_RT, end_RT = st.select_slider(
    'Select a range of retention time, mins',
    options=final_df.columns.to_list(),
    value=(final_df.columns.min(), final_df.columns.max()))
    st.write ('You selected RT starting from', start_RT, 'to', end_RT)

    option = st.selectbox(
    'Please select relative peak for RRT calculation,mins (should be within selected range)',
    (final_df.columns.to_list()))

    st.write('You selected relative peak:', option)
    #RP check

    reference_in_range = start_RT <= option <= end_RT
    if not reference_in_range:
        st.error(f'Relative time {option} is outside the range! Adjust the range or reference peak to continue.')

    if reference_in_range and st.button('Generate SP3 table'):
        # Only include peaks that were part of the table above (respecting any LCAP
        # peak exclusions), restricted to the selected RT range.
        included_rts = set(final_df.columns.to_list())
        selected_columns = [
            col for col in merged_df.columns
            if isinstance(col, (int, float)) and col in included_rts and start_RT <= col <= end_RT
        ]
        selected_data = merged_df[selected_columns].copy()

        # Calculate the sum of each row, find the ratio, and convert to percentage
        row_sums = selected_data.sum(axis=1)
        selected_data = selected_data.div(row_sums, axis=0) * 100

        selected_data = selected_data.round(2)

        #Calulate RRT
        original_columns = selected_data.columns.tolist()
        new_columns = [round(col / option, 2) if isinstance(col, (int, float)) else col for col in original_columns]

        # Create a MultiIndex
        multi_index = pd.MultiIndex.from_arrays(
            [
                [f"RT {rt}" for rt in original_columns], 
                [f"RRT {rrt}" for rrt in new_columns]
            ], 
            names=['RT', 'RRT']
        )

        # Set MultiIndex for the columns
        selected_data.columns = multi_index

        # Download SP3 table
        st.download_button(
            label="Download SP3.xlsx table",
            data=convert_df_to_excel(selected_data),
            file_name="SP3 table.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Display the final DataFrame in the app
        st.dataframe(selected_data)

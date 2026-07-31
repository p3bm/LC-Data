import streamlit as st
from PIL import Image
import pandas as pd
from io import BytesIO

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
        2. App checks which opton was selected in the radiobox and then parses the "Area" or "LCAP" column.
        2. It parses only "Sample", "RT (mins)" and "Area or LCAP" column and ignores "Peak Label".
        3. "RT (mins)" are rounded to the second decimal places (e.g. 1.23).
        4. The table is transposed and grouped by "Sample" index and "RTs" columns.
        5. All absent data is filled by zeros. It happens when a peak is absent in one sample but present in another.
        6. Hard part: To solve the problem of peak drift between samples. The app compares the "RTs" and if the difference is ≤0.02, the columns are merged.
        The final RT is the highest of the two. After merging 3.25 and 3.26 mins columns, it will keep only 3.26.
        Merge works only if at least one value in each row across these columns is 0.
        7. It then drops the excess columns that are no longer needed after the merge.
        8. And finally it exports the DataFrame (which is shown on the screen) to Excel that you can download 🔚\\
        **Creation of SP3 table**
        1. Then the app takes the index row of table and converts it to a list.
        2. After that it creates a slider based on this list.
        3. Additional selection of reference peak is depends on the list from step 1. Then it takes input value.
        4. Range and refernce values are saved to the variable and taken into account after pressing button.
        5. During processing script delete excess column amd then recalculate LCAP based on it's total sum of row.
        6. Then simple data export to show and download table.
    ''')

uploaded_file = st.file_uploader("Upload your *.txt* file")

# File uploader

# Function to convert DataFrame to Excel file in memory
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True)
        writer.book.close()  # Save the workbook
    return output.getvalue()  # Get the binary content


if uploaded_file is not None:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file, sep='\t', engine='python')
    # Rounding the 'RT (mins)' column to the nearest hundredth
    df['RT (mins)'] = df['RT (mins)'].round(2)

    # Pivoting the DataFrame
    # Each unique rounded 'RT (mins)' value becomes a column
    pivot_df = df.pivot_table(index='Sample Name', 
                        columns='RT (mins)', 
                        values="Area")

    #Filling NaN values with zero
    pivot_df.fillna(0, inplace=True)

    df=pivot_df
    merged_df = pd.DataFrame(index=df.index)
    columns_to_drop = set()  # Store columns that should be dropped after merging

    do_merge = st.toggle("Merge peaks with similar RTs (to account for RT drift across samples)")

    if do_merge:

        threshold = st.number_input("Set the threshold for merging peaks (in minutes)", min_value=0.001, max_value=0.100, value=0.020, step=0.001, format="%0.3f")
        
        # Iterate through each pair of columns and check for merging condition
        for rt1 in df.columns:
            for rt2 in df.columns:
                if rt1 != rt2 and rt1 not in columns_to_drop and rt2 not in columns_to_drop:
                    try:
                        # Check the difference between rt1 and rt2 is within the specified range
                        if abs(float(rt1) - float(rt2)) <= threshold:
                            # Check if at least one value in each row across these columns is 0
                            condition = (df[rt1] == 0.0) | (df[rt2] == 0.0)
                            if condition.any():  # If the condition is true for any row
                                # Sum the columns and use the higher RT value as the column name
                                new_col_name = max(rt1, rt2, key=lambda x: float(x))
                                merged_df[new_col_name] = df[[rt1, rt2]].sum(axis=1)
                                # Mark columns for dropping
                                columns_to_drop.update([rt1, rt2])
                    except ValueError:
                        # Handle cases where rt1 or rt2 cannot be converted to float
                        continue
    
        # Drop the processed columns from df
        df.drop(columns=list(columns_to_drop), inplace=True)

    # Add the remaining columns that were not merged to merged_df
    for col in df.columns:
        if col not in merged_df:
            merged_df[col] = df[col]

    # Sort the columns as they might be out of order after merging
    merged_df = merged_df.sort_index(axis=1)
    merged_df = merged_df.round(2)
    
    for col in merged_df.columns:
        old_name = col
        new_name = "RT " + str(col.round(2))
        merged_df = merged_df.rename(columns={old_name:new_name})

    calculate_lcap = st.toggle("Calculate LCAP (Relative Peak Area) from the merged data")

    if not calculate_lcap:
        st.dataframe(merged_df)
        final_df = merged_df
    else:
        # Identify retention time columns
        numeric_cols = merged_df.select_dtypes(include='number').columns.tolist() # find numeric columns and convert to list
        peak_area_data = merged_df[numeric_cols] # splits into just numeric values

        # Creates a single-row DataFrame of checkboxes (True by default)
        col_selector_df = pd.DataFrame([True] * len(numeric_cols), index=numeric_cols).T 
        col_selector_df.index = ["Include"]

        st.write("Select Retention Times to Include in LCAP:")
        edited_selector = st.data_editor(
            col_selector_df,
            use_container_width=True,
            column_config={col: st.column_config.CheckboxColumn(required=True) for col in numeric_cols}
        )

        # Get selected columns from checkbox row
        selected_cols = [col for col in numeric_cols if edited_selector.iloc[0][col]]

        if not selected_cols:
            st.warning("Please select at least one retention time to calculate LCAP.")

        # Calculates LCAP from selected peaks
        selected_data = peak_area_data[selected_cols]
        total_areas = selected_data.sum(axis=1)
        lcap_data = selected_data.div(total_areas, axis=0) * 100

        lcap_results = lcap_data.round(1)
        st.dataframe(lcap_results)

        final_df = lcap_results

    # Download intermediate table
    st.download_button(
        label="Download full table",
        data=convert_df_to_excel(final_df),
        file_name="Area_RT.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown('''
    Now we can create SP3 table with LCAP and RRT
    ''')
    st.latex(r'''
    LCAP=\frac{A_{i}}{ \sum A }\qquad RRT= \frac{RT_{analyte}}{RT_{reference}}
    ''')
    
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

    if not start_RT <= option <= end_RT:
        st.error(f'Relative time {option} is outside the range!')

    if st.button('Generate SP3 table'):
        # Select range of columns by min and max value and delete the rest
        selected_columns = [col for col in merged_df.columns if isinstance(col, (int, float)) and start_RT <= col <= end_RT]
        selected_data = merged_df[selected_columns]

        # Calculate the sum of each row, find the ratio, and convert to percentage
        row_sums = selected_data.iloc[:,:].sum(axis=1)
        for col in selected_columns:
            selected_data.loc[:, col] = (selected_data[col] / row_sums) * 100

        selected_data = selected_data.round(2)
        
        #Calulate RRT
        original_columns = selected_data.columns.tolist()
        new_columns = [round(col / option, 2) if isinstance(col, (int, float)) else col for col in original_columns]

        # Create a MultiIndex
        multi_index = pd.MultiIndex.from_arrays([original_columns, new_columns], names=['RT', 'RRT'])

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

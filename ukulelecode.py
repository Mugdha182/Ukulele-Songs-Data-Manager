import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import ttkbootstrap as ttkb

# Global variables to hold data and canvas
data = None
filtered_data = None
current_canvas = None

# Load and validate data from CSV files
def load_data(file_paths, required_columns):
    global data
    data = {}
    for name, path in file_paths.items():
        try:
            if not path:
                raise ValueError(f"No file path provided for {name}.csv")
            df = pd.read_csv(path)

            # Check for required columns in tabdb
            if name == 'tabdb':
                missing_cols = [col for col in required_columns if col not in df.columns]
                if missing_cols:
                    raise ValueError(f"{name}.csv missing columns: {missing_cols}")

            # Process tabdb columns
            if name == 'tabdb':
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
                if 'duration' in df.columns:
                    df['duration'] = pd.to_timedelta(df['duration'], errors='coerce').dt.total_seconds()
                if 'year' in df.columns:
                    df['year'] = pd.to_numeric(df['year'], errors='coerce')
                if 'difficulty' in df.columns:
                    df['difficulty'] = pd.to_numeric(df['difficulty'], errors='coerce')

            # Process playdb data to transform and add play order column
            if name == 'playdb':
                # Convert wide format to long format and transform the playdb data
                df = transform_playdb_data(df)
                # Add the play order column to the transformed data
                df = add_play_order_column(df)

            # Transform requestdb to long format
            if name == 'requestdb':
                df = transform_requestdb_data(df)

            data[name] = df
        except Exception as e:
            messagebox.showerror("Error", f"Error loading {name}.csv: {e}")
            return None
    return data

def transform_playdb_data(playdb):
    # Convert wide format to long format for playdb
    playdb_long = playdb.melt(id_vars=['song', 'artist'], var_name='date', value_name='play_order')
    playdb_long = playdb_long.dropna(subset=['play_order'])  # Drop rows where play_order is NaN

    # Convert 'date' to datetime format for easier filtering
    playdb_long['date'] = pd.to_datetime(playdb_long['date'], format='%Y%m%d', errors='coerce')

    # Sort by date and play order
    playdb_long = playdb_long.sort_values(by=['date', 'play_order'])

    # Reset index
    playdb_long.reset_index(drop=True, inplace=True)

    return playdb_long

def transform_requestdb_data(requestdb):
    # Convert wide format to long format for requestdb
    requestdb_long = requestdb.melt(id_vars=['song', 'artist'], var_name='date', value_name='requested_by')
    requestdb_long = requestdb_long.dropna(subset=['requested_by'])  # Drop rows where requested_by is NaN

    # For easier merging convert 'date' to datetime format 
    requestdb_long['date'] = pd.to_datetime(requestdb_long['date'], format='%Y%m%d')

    # Replace 'G' with 'Group' and 'A' with 'Audience'
    requestdb_long['requested_by'] = requestdb_long['requested_by'].replace({'G': 'Group', 'A': 'Audience', '?': 'Unknown'})

    return requestdb_long


# Add a new function to compute the order of songs played
def add_play_order_column(playdb):
    # Sort playdb by 'date' and assign an order of the song played
    playdb_sorted = playdb.sort_values(by=['date', 'play_order']).copy()
    playdb_sorted['order_of_song_played'] = playdb_sorted.groupby('date').cumcount() + 1
    return playdb_sorted

# Merge playdb and requestdb data
def merge_playdb_requestdb():
    if 'playdb' not in data or 'requestdb' not in data:
        messagebox.showerror("Error", "Both playdb and requestdb data must be loaded to merge.")
        return None

    playdb = data['playdb']
    requestdb = data['requestdb']

    common_columns = ['song', 'artist']  # Adjust this list to match relevant columns

    # Merge the two tables on the common columns, retaining all data with suffixes
    merged_df = pd.merge(playdb, requestdb, on=common_columns, how='outer', suffixes=('_playdb', '_requestdb'))

    # Dictionary to store combined data for each column, so we can later concatenate all at once
    combined_columns = {}

    # Loop through each column and combine values from playdb and requestdb where they exist
    for col in playdb.columns:
        if col not in common_columns:
            # Combine values from both DataFrames into lists, handling missing values as needed
            combined_columns[col] = merged_df[[f'{col}_playdb', f'{col}_requestdb']].apply(lambda x: x.dropna().tolist(), axis=1)

    # Create a new DataFrame for the combined columns, keeping common columns intact
    combined_df = pd.concat([merged_df[common_columns], pd.DataFrame(combined_columns)], axis=1)

    # Make a copy to avoid fragmentation
    final_df = combined_df.copy()

    return final_df


# Function to filter tabdb data based on user criteria and range filters
def filter_tabdb_data():
    global filtered_data
    if data is None or 'tabdb' not in data or 'playdb' not in data or 'requestdb' not in data:
        messagebox.showerror("Error", "Data is not loaded. Please load the data first.")
        return

    tabdb = data['tabdb'].copy()
    playdb = data['playdb'].copy()
    requestdb = data['requestdb'].copy()

    filtered_data = tabdb.copy()

    # Year range filter
    if year_start_entry.get() and year_end_entry.get():
        try:
            start_year = int(year_start_entry.get())
            end_year = int(year_end_entry.get())
            filtered_data = filtered_data[(filtered_data['year'] >= start_year) & (filtered_data['year'] <= end_year)]
        except ValueError:
            messagebox.showwarning("Warning", "Invalid year range format. Skipping year filter.")

    # Difficulty range filter
    if difficulty_range_entry.get():
        try:
            min_diff, max_diff = map(float, difficulty_range_entry.get().split(','))
            filtered_data = filtered_data[(filtered_data['difficulty'] >= min_diff) & (filtered_data['difficulty'] <= max_diff)]
        except ValueError:
            messagebox.showwarning("Warning", "Invalid difficulty range format. Skipping difficulty filter.")

    # Date range filter
    if date_range_entry.get():
        try:
            start_date, end_date = map(lambda x: pd.to_datetime(x.strip()), date_range_entry.get().split(','))
            filtered_data = filtered_data[(filtered_data['date'] >= start_date) & (filtered_data['date'] <= end_date)]
        except Exception as e:
            messagebox.showwarning("Warning", f"Invalid date range format or filtering error: {e}")
            return

    # Language filter
    selected_languages = [language_listbox.get(i) for i in language_listbox.curselection()]
    if "All" not in selected_languages and selected_languages:
        filtered_data = filtered_data[filtered_data['language'].isin(selected_languages)]

    # Apply categorical filters
    selected_genders = [gender_listbox.get(i) for i in gender_listbox.curselection()]
    if "All" not in selected_genders and selected_genders:
        filtered_data = filtered_data[filtered_data['gender'].isin(selected_genders)]

    selected_tabbbers = [tabber_listbox.get(i) for i in tabber_listbox.curselection()]
    if "All" not in selected_tabbbers and selected_tabbbers:
        filtered_data = filtered_data[filtered_data['tabber'].isin(selected_tabbbers)]

    selected_sources = [source_listbox.get(i) for i in source_listbox.curselection()]
    if "All" not in selected_sources and selected_sources:
        filtered_data = filtered_data[filtered_data['source'].isin(selected_sources)]

    if type_filter.get() != "All":
        filtered_data = filtered_data[filtered_data['type'] == type_filter.get()]

    # Merge with playdb to get the order of the song played
    merged_data = pd.merge(filtered_data, playdb[['song', 'date', 'order_of_song_played']], on=['song', 'date'], how='left')

    # Merge with requestdb to get the requested_by information
    merged_data = pd.merge(merged_data, requestdb[['song', 'date', 'requested_by']], on=['song', 'date'], how='left')

    # Display the number of rows in the filtered data
    row_count_label.config(text=f"Number of Rows: {len(filtered_data)}")

    # Sort merged data by descending date initially
    if 'date' in merged_data.columns:
        merged_data = merged_data.sort_values(by='date', ascending=False)

    # Update filtered_data to merged_data
    filtered_data = merged_data
    display_table(filtered_data)

# Function to display filtered data in a table
def display_table(filtered_tabdb):
    # Update sorting column options
    sort_column_combo['values'] = list(filtered_tabdb.columns)

    # Clear the previous entries 
    for row in tree.get_children():
        tree.delete(row)

    # Set up the table columns
    tree["column"] = list(filtered_tabdb.columns)
    tree["show"] = "headings"

    for column in tree["column"]:
        tree.heading(column, text=column)
        tree.column(column, width=130, anchor='center')

    # Insert new rows 
    for _, row in filtered_tabdb.iterrows():
        tree.insert("", "end", values=list(row))
        
# Sort the filtered data
def sort_filtered_data(order):
    global filtered_data
    if filtered_data is None or filtered_data.empty:
        messagebox.showerror("Error", "No filtered data available to sort. Please apply filters first.")
        return

    # Select column to sort
    column_to_sort = sort_column_combo.get()  # Updated to the correct variable name
    if column_to_sort == "Select Column":
        messagebox.showerror("Error", "Please select a column to sort by.")
        return

    # Sort data in the specified order
    ascending = True if order == "Ascending" else False
    filtered_data = filtered_data.sort_values(by=column_to_sort, ascending=ascending)
    display_table(filtered_data)


# Generate specified plots and embed them in the plot selection frame
def generate_plots(plot_type):
    global current_canvas

    if filtered_data is None:
        messagebox.showerror("Error", "No filtered data available. Please apply filters first.")
        return

    # Clear previous plot if it exists
    if current_canvas:
        current_canvas.get_tk_widget().pack_forget()
        current_canvas = None

    # Create figure for the plot
    fig, ax = plt.subplots(figsize=(10, 12))

    if plot_type == "difficulty":
        sns.histplot(filtered_data['difficulty'].dropna(), bins=5, ax=ax)
        ax.set_title("Histogram of Songs by Difficulty Level")
        ax.set_xlabel("Difficulty Level")
        ax.set_ylabel("Count")
    elif plot_type == "duration":
        sns.histplot(filtered_data['duration'].dropna() / 60, kde=True, ax=ax)  # Convert to minutes
        ax.set_title("Histogram of Songs by Duration (minutes)")
        ax.set_xlabel("Duration (minutes)")
        ax.set_ylabel("Count")
    elif plot_type == "language":
        filtered_data['language'].value_counts().plot(kind='bar', ax=ax)
        ax.set_title("Bar Chart of Songs by Language")
        ax.set_xlabel("Language")
        ax.set_ylabel("Count")
    elif plot_type == "source":
        filtered_data['source'].value_counts().plot(kind='bar', ax=ax)
        ax.set_title("Bar Chart of Songs by Source")
        ax.set_xlabel("Source")
        ax.set_ylabel("Count")
    elif plot_type == "decade":
        filtered_data['decade'] = (filtered_data['year'] // 10) * 10
        filtered_data['decade'].value_counts().sort_index().plot(kind='bar', ax=ax)
        ax.set_title("Bar Chart of Songs by Decade")
        ax.set_xlabel("Decade")
        ax.set_ylabel("Count")
    elif plot_type == "date":
        play_counts = filtered_data['date'].value_counts().sort_index().cumsum()
        play_counts.plot(ax=ax)
        ax.set_title("Cumulative Songs Played by Date")
        ax.set_xlabel("Date")
        ax.set_ylabel("Cumulative Count")
    elif plot_type == "gender":
        # Clean and standardize the gender column
        filtered_data['gender'] = filtered_data['gender'].str.strip().str.capitalize()
        # Update gender plot to use a legend instead of overlapping labels
        filtered_data['gender'].value_counts().plot(
            kind='pie',
            autopct='%1.1f%%',
            ax=ax,
            startangle=90,
            wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
            textprops={'fontsize': 10}
        )
        ax.set_title("Pie Chart of Songs by Gender")
        ax.set_ylabel('')
        ax.legend(
            loc='upper left',
            bbox_to_anchor=(1.0, 0.8),  # Adjust position to avoid overlap
            title='Gender'
        )

    # Adjust layout to reduce white space
    plt.tight_layout()  # Automatically adjusts to minimize white space
    fig.subplots_adjust(top=0.9, bottom=0.2)  # Further adjustments for better alignment

    # Embed the plot in the tkinter window
    current_canvas = FigureCanvasTkAgg(fig, master=plot_selection_frame)
    current_canvas.draw()
    current_canvas.get_tk_widget().pack()


# Function to refresh data (clear filters and reset UI)
def refresh_data():
    global data, filtered_data
    data = None
    filtered_data = None

    # Clear all input fields and selections
    year_start_entry.delete(0, tk.END)
    year_end_entry.delete(0, tk.END)
    difficulty_range_entry.delete(0, tk.END)
    tabdb_entry.delete(0, tk.END)
    playdb_entry.delete(0, tk.END)
    requestdb_entry.delete(0, tk.END)
    date_range_entry.delete(0, tk.END)

    # Reset comboboxes
    type_filter.set("All")
    sort_column_combo.set("Select Column")

    # Clear listbox selections
    tabber_listbox.selection_clear(0, tk.END)
    source_listbox.selection_clear(0, tk.END)
    language_listbox.selection_clear(0, tk.END)
    gender_listbox.selection_clear(0, tk.END)

    # Clear table (Treeview)
    for row in tree.get_children():
        tree.delete(row)

    # Reset row count label
    row_count_label.config(text="Number of Rows: 0")

# Make sure to also update the button to call this updated refresh_data function


# Function to save all plots to a single PDF
def save_plots_to_pdf():
    if filtered_data is None or filtered_data.empty:
        messagebox.showerror("Error", "No filtered data available. Please apply filters first.")
        return

    # Define the file path to save the PDF
    file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])

    if not file_path:
        return  # Exit if no file path is provided

    with PdfPages(file_path) as pdf:
        # List of plot types to generate
        plot_types = [
            ("difficulty", "Histogram of Songs by Difficulty Level"),
            ("duration", "Histogram of Songs by Duration"),
            ("language", "Bar Chart of Songs by Language"),
            ("source", "Bar Chart of Songs by Source"),
            ("decade", "Bar Chart of Songs by Decade"),
            ("date", "Cumulative Songs Played by Date"),
            ("gender", "Pie Chart of Songs by Gender")
        ]

        # Generate and save each plot to the PDF
        for plot_type, plot_label in plot_types:
            fig, ax = plt.subplots(figsize=(9, 7))

            # Generate each plot separately for PDF saving
            if plot_type == "difficulty":
                sns.histplot(filtered_data['difficulty'].dropna(), bins=5, ax=ax)
                ax.set_title(plot_label)
                ax.set_xlabel("Difficulty Level")
                ax.set_ylabel("Count")
            elif plot_type == "duration":
                sns.histplot(filtered_data['duration'].dropna() / 60, kde=True, ax=ax)  # Convert to minutes
                ax.set_title(plot_label)
                ax.set_xlabel("Duration (minutes)")
                ax.set_ylabel("Count")
            elif plot_type == "language":
                filtered_data['language'].value_counts().plot(kind='bar', ax=ax)
                ax.set_title(plot_label)
                ax.set_xlabel("Language")
                ax.set_ylabel("Count")
            elif plot_type == "source":
                filtered_data['source'].value_counts().plot(kind='bar', ax=ax)
                ax.set_title(plot_label)
                ax.set_xlabel("Source")
                ax.set_ylabel("Count")
            elif plot_type == "decade":
                filtered_data['decade'] = (filtered_data['year'] // 10) * 10
                filtered_data['decade'].value_counts().sort_index().plot(kind='bar', ax=ax)
                ax.set_title(plot_label)
                ax.set_xlabel("Decade")
                ax.set_ylabel("Count")
            elif plot_type == "date":
                play_counts = filtered_data['date'].value_counts().sort_index().cumsum()
                play_counts.plot(ax=ax)
                ax.set_title(plot_label)
                ax.set_xlabel("Date")
                ax.set_ylabel("Cumulative Count")
            elif plot_type == "gender":
                filtered_data['gender'].value_counts().plot(
                    kind='pie',
                    autopct='%1.1f%%',
                    ax=ax,
                    startangle=90,
                    wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
                    textprops={'fontsize': 10}
                )
                ax.set_title(plot_label)
                ax.set_ylabel('')
                ax.legend(
                    loc='upper left',
                    bbox_to_anchor=(1.0, 0.8),
                    title='Gender'
                )

            # Save the figure to the PDF
            pdf.savefig(fig)
            plt.close(fig)

    messagebox.showinfo("Success", f"All plots have been saved to {file_path}")

# Function to load and initialize data
def load_and_initialize():
    file_paths = {
        'tabdb': tabdb_entry.get(),
        'playdb': playdb_entry.get(),
        'requestdb': requestdb_entry.get()
    }

    required_columns = [
        'song', 'artist', 'year', 'type', 'gender', 'duration',
        'language', 'tabber', 'source', 'date', 'difficulty', 'specialbooks'
    ]

    if load_data(file_paths, required_columns):
        messagebox.showinfo("Success", "Data loaded successfully.")

# Function to select file path for loading
def select_file(entry):
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    entry.delete(0, tk.END)
    entry.insert(0, file_path)

# Function to show the User Manual Frame
def show_user_manual_frame():
    welcome_frame.pack_forget()
    main_frame.pack_forget()
    plot_selection_frame.pack_forget()
    user_manual_frame.pack(fill=tk.BOTH, expand=True)
    user_manual_frame.pack(fill=tk.BOTH, expand=True)
    
# Function to navigate to the welcome frame
def show_welcome_frame():
    main_frame.pack_forget()
    plot_selection_frame.pack_forget()
    user_manual_frame.pack_forget()  # Add this line to hide the user manual frame
    welcome_frame.pack(fill=tk.BOTH, expand=True)

# Function to navigate to the main frame (filtering page)
def show_main_frame():
    welcome_frame.pack_forget()
    plot_selection_frame.pack_forget()
    main_frame.pack(fill=tk.BOTH, expand=True)

# Function to navigate to the plot selection frame (plot graphs page)
def show_plot_selection_frame():
    welcome_frame.pack_forget()
    main_frame.pack_forget()
    plot_selection_frame.pack(fill=tk.BOTH, expand=True)

# Main tkinter application setup
app = ttkb.Window(themename="solar")
app.title("Ukulele Tuesday Data Manager")
app.state('zoomed')

# Welcome Frame
welcome_frame = tk.Frame(app,bg='#264653')
welcome_frame.pack(fill=tk.BOTH, expand=True)

# Welcome message
welcome_label = tk.Label(welcome_frame, text="Welcome to Ukulele Tuesday Data Manager", font=("Helvetica", 26, 'bold'), bg='#264653', fg='white')
welcome_label.pack(pady=30)

# User instructions
instructions_label = tk.Label(
    welcome_frame,
    text="This tool helps you explore and visualize data related to our Ukulele sessions.",
    font=("Georgia", 18),
    bg='#264653',
    fg='white'
)
instructions_label.pack(pady=10)

# Progress bar or icon-based steps (Vertical Layout)
progress_frame = tk.Frame(welcome_frame, bg='#264653')
progress_frame.pack(pady=30)

# Box around all workflow steps (in a single unified box)
workflow_box = tk.LabelFrame(
    welcome_frame,
    text="Features",
    font=("Helvetica", 18, 'bold'),
    bg='#1D3557',  # Changed to make it more distinct
    fg='white',
    bd=5,  # Increased border width for better visibility
    relief=tk.GROOVE,  # Use 'GROOVE' for a more pronounced effect
    padx=20,
    pady=15
)
workflow_box.pack(pady=30, padx=30, fill=tk.BOTH, expand=False)

# Workflow steps inside the box
workflow_text = """
1: Explore Data
    → View song details and data by applying required filters. 

2: User Manual
    → Overview of how to navigate through the application.

3: Save Plots to PDF 
    → Creates a PDF of all the plots generated.
"""

workflow_label = tk.Label(
    workflow_box,
    text=workflow_text,
    font=("Helvetica", 16),
    bg='#1D3557',  # Match background color to workflow_box
    fg='white',
    justify=tk.LEFT
)
workflow_label.pack()

def on_enter(e):
    e.widget['background'] = '#D1E7DD'  # Light green background when hovered
    e.widget['foreground'] = '#1B4332'  # Dark green text

def on_leave(e):
    e.widget['background'] = e.widget.defaultBackground  # Restore original background color
    e.widget['foreground'] = e.widget.defaultForeground  # Restore original text color

# Define a helper function to apply hover effects to buttons
def apply_hover_effects(button):
    button.defaultBackground = button['background']
    button.defaultForeground = button['foreground']
    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
    
# "Explore Data" Button
explore_data_button = tk.Button(
    welcome_frame,
    text="Explore Data",
    command=show_main_frame,
    font=("Helvetica", 16,'bold'),
    bg='#FFC107',  # Initial button color (Yellow)
    fg='black'  # Initial text color
)
explore_data_button.pack(pady=10)
apply_hover_effects(explore_data_button)

# "User Manual" Button
user_manual_button = tk.Button(
    welcome_frame,
    text="User Manual",
    command=show_user_manual_frame,
    font=("Helvetica", 16,'bold'),
    bg='#FFC107',  # Initial button color (Yellow)
    fg='black'  # Initial text color
)
user_manual_button.pack(pady=10)
apply_hover_effects(user_manual_button)

# User Manual Frame
user_manual_frame = ttkb.Frame(app, style='Main.TFrame')

# Title for User Manual
user_manual_title = ttkb.Label(
    user_manual_frame,
    text="User Manual",
    font=("Helvetica", 16,'bold'),
    style="Title.TLabel"
)
user_manual_title.pack(pady=20)

# Scrollable Text Box for User Manual
manual_text_frame = ttkb.Frame(user_manual_frame, style='Section.TFrame')
manual_text_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

scrollbar = ttkb.Scrollbar(manual_text_frame, orient=tk.VERTICAL)
manual_textbox = tk.Text(
    manual_text_frame,
    wrap=tk.WORD,
    font=("Helvetica", 12,'bold'),
    yscrollcommand=scrollbar.set,
    bg="#F1FAEE",
    fg="#1D3557"
)
scrollbar.config(command=manual_textbox)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
manual_textbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# User Manual Content
user_manual_content = """
Welcome to Ukulele Tuesday Data Manager!

This program helps you load, merge, analyze, and visualize song data using filters and interactive graphs.

Features:
*Explore Data Page*
1. Load Data:
   - Upload the required CSV files accordingly.
   - Ensure valid file formats and required columns.

2. Filter & Sort Data:
   - Use filters like Year, Difficulty, Dates, Type(of artist), Tabber(person who tabbed the song), Language, Gender, and Source to segment your data.
   - Select specific filters and sorting and apply them to focus on relevant data.
   - Tabber, Language, Gender, and Source have multiple selections.

*Show Selection Plot Page*
1. Visualize Data:
   - Generate graphs: histograms, bar charts, pie charts, and cumulative line plots.
   
2. Save Plots:
   - Export all generated plots as a PDF with required name using the 'Save All Plots to PDF' button to a desired location.

*User Manual Page*
1. User-friendly flow of the application.

Navigation:
- Explore Data: Apply filters, sort and explore song details interactively.
- Show Plot Selection: Navigates to the page that creates innovative graphs.
- User Manual: Access these instructions for guidance.
- Home: Navigate back to the main screen.
- Previous: Goes back to Explore Data Page.

Requirements:
- Before running the python code, please ensure the following python libraries are installed: pandas, matplotlib, seaborn, tkinter, ttkbootstrap 

Enjoy exploring your Ukulele Tuesday data!

                  🎵 Strumming through the strings of data, turning melodies into insights – the Ukulele Data Manager is where music meets meaning! 🎶

"""





# Insert the user manual content into the text box
manual_textbox.insert(tk.END, user_manual_content)
manual_textbox.config(state=tk.DISABLED)  # Make the text read-only

# Back to Home Button
home_button = tk.Button(
    user_manual_frame, 
    text="Home", 
    font=("Helvetica", 12, "bold"), 
    command=show_welcome_frame, 
    width=8,  # Set the width for consistency
    bg="#F4A261",  # Default background color
    fg="white"  # Default text color
)
home_button.pack(pady=15)  # Add padding
apply_hover_effects(home_button)  # Apply hover effects


# Main Frame (Filter Data Page)
main_frame = tk.Frame(app)

frame_files = tk.Frame(main_frame)
frame_files.pack(pady=10)
frame_filters = tk.Frame(main_frame)
frame_filters.pack(pady=10)
frame_display = tk.Frame(main_frame)
frame_display.pack(pady=10, fill=tk.BOTH, expand=True)

# File path selection with adjusted alignment
tk.Label(frame_files, text="Enter tabbed songs data path:", font=("Helvetica", 10, 'bold'), anchor='e', justify='right').grid(row=0, column=0, padx=(20, 5), sticky='e')
tabdb_entry = tk.Entry(frame_files, width=40)
tabdb_entry.grid(row=0, column=1, padx=5)

browse_tabdb_button = tk.Button(frame_files, text="Browse", font=("Helvetica", 10, 'bold'), command=lambda: select_file(tabdb_entry))
browse_tabdb_button.grid(row=0, column=2)
apply_hover_effects(browse_tabdb_button)

tk.Label(frame_files, text="Enter songs played on Tuesday data path:", font=("Helvetica", 10, 'bold'), anchor='e', justify='right').grid(row=1, column=0, padx=(20, 5), sticky='e')
playdb_entry = tk.Entry(frame_files, width=40)
playdb_entry.grid(row=1, column=1, padx=5)

browse_playdb_button = tk.Button(frame_files, text="Browse", font=("Helvetica", 10, 'bold'), command=lambda: select_file(playdb_entry))
browse_playdb_button.grid(row=1, column=2)
apply_hover_effects(browse_playdb_button)

tk.Label(frame_files, text="Enter requested songs data path:", font=("Helvetica", 10, 'bold'), anchor='e', justify='right').grid(row=2, column=0, padx=(20, 5), sticky='e')
requestdb_entry = tk.Entry(frame_files, width=40)
requestdb_entry.grid(row=2, column=1, padx=5)

browse_requestdb_button = tk.Button(frame_files, text="Browse", font=("Helvetica", 10, 'bold'), command=lambda: select_file(requestdb_entry))
browse_requestdb_button.grid(row=2, column=2)
apply_hover_effects(browse_requestdb_button)

# Load Data Button - Placing it just below the file path inputs
load_data_button = tk.Button(frame_files, text="Load Data", font=("Helvetica", 10, 'bold'),command=load_and_initialize)
load_data_button.grid(row=3, column=1, pady=10, sticky='w')
apply_hover_effects(load_data_button)

# Create a new frame specifically for the Year Range entries
year_range_frame = tk.Frame(frame_filters)
year_range_frame.grid(row=0, column=1, columnspan=3, sticky='w', padx=(5, 5), pady=5)

# Filtering criteria
tk.Label(frame_filters, text="Year Range in format yyyy (start,end):", font=("Helvetica", 10, 'bold')).grid(row=0, column=0, padx=(5, 2), sticky="w")

# Start Year Entry with spacing inside the new frame
year_start_entry = tk.Entry(year_range_frame, width=15)
year_start_entry.grid(row=0, column=0, padx=(0, 5))

# "to" Label within the new frame
tk.Label(year_range_frame, text="to").grid(row=0, column=1, padx=(5, 5))

# End Year Entry within the new frame
year_end_entry = tk.Entry(year_range_frame, width=15)
year_end_entry.grid(row=0, column=2, padx=(5, 0))

tk.Label(frame_filters, text="Difficulty Range from 1-6 (min,max):", font=("Helvetica", 10, 'bold'), anchor='e', justify='right').grid(row=1, column=0, padx=5, sticky="e")
difficulty_range_entry = tk.Entry(frame_filters, width=20)
difficulty_range_entry.grid(row=1, column=1, padx=5, columnspan=3)

tk.Label(frame_filters, text="Date Range in format yyyy-mm-dd (start,end):", font=("Helvetica", 10, 'bold'), anchor='e', justify='right').grid(row=2, column=0, padx=5, sticky="e")
date_range_entry = tk.Entry(frame_filters, width=20)
date_range_entry.grid(row=2, column=1, padx=5, columnspan=3)

tk.Label(frame_filters, text="Type:", font=("Helvetica", 10, 'bold'), anchor='e', justify='right').grid(row=4, column=0, padx=5, sticky="e")
type_filter = ttk.Combobox(frame_filters, values=["All", "Group", "Person"], state="readonly")
type_filter.grid(row=4, column=1, padx=5, columnspan=3)
type_filter.set("All")


# Gender listbox with scrollbar for multiple selection
tk.Label(frame_filters, text="Gender:",font=("Helvetica", 10, 'bold')).grid(row=7, column=5, padx=5)

gender_frame = tk.Frame(frame_filters)
gender_frame.grid(row=7, column=6, padx=5, columnspan=3)

gender_scrollbar = tk.Scrollbar(gender_frame, orient="vertical")
gender_listbox = tk.Listbox(gender_frame, selectmode="multiple", height=4, yscrollcommand=gender_scrollbar.set, exportselection=False)

gender_scrollbar.config(command=gender_listbox.yview)
gender_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
gender_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Adding gender values
for item in ["All", "male", "female", "duet","ensemble","instrumental"]:
    gender_listbox.insert(tk.END, item)

# Source listbox with scrollbar for multiple selection
tk.Label(frame_filters, text="Source:",font=("Helvetica", 10, 'bold')).grid(row=7, column=0, padx=5)

source_frame = tk.Frame(frame_filters)
source_frame.grid(row=7, column=1, padx=5, columnspan=3)

source_scrollbar = tk.Scrollbar(source_frame, orient="vertical")
source_listbox = tk.Listbox(source_frame, selectmode="multiple", height=4, yscrollcommand=source_scrollbar.set, exportselection=False)

source_scrollbar.config(command=source_listbox.yview)
source_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
source_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

for item in ["All", "new", "old", "off"]:
    source_listbox.insert(tk.END, item)

# Tabber listbox with scrollbar for multiple selection
tk.Label(frame_filters, text="Tabber:",font=("Helvetica", 10, 'bold')).grid(row=5, column=0, padx=5)

tabber_frame = tk.Frame(frame_filters)
tabber_frame.grid(row=5, column=1, padx=5, columnspan=3)

tabber_scrollbar = tk.Scrollbar(tabber_frame, orient="vertical")
tabber_listbox = tk.Listbox(tabber_frame, selectmode="multiple", height=6, yscrollcommand=tabber_scrollbar.set, exportselection=False)

tabber_scrollbar.config(command=tabber_listbox.yview)
tabber_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
tabber_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

for item in ["All", "Bastien", "Bea", "Mischa", "Annalisa", "Jeremie", "Joh", "Caroline", "Kirsten"]:
    tabber_listbox.insert(tk.END, item)

# Language listbox with scrollbar for multiple selection
tk.Label(frame_filters, text="Language:",font=("Helvetica", 10, 'bold')).grid(row=5, column=5, padx=5)

language_frame = tk.Frame(frame_filters)
language_frame.grid(row=5, column=6, padx=5, columnspan=3)

language_scrollbar = tk.Scrollbar(language_frame, orient="vertical")
language_listbox = tk.Listbox(language_frame, selectmode="multiple", height=6, yscrollcommand=language_scrollbar.set, exportselection=False)

language_scrollbar.config(command=language_listbox.yview)
language_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
language_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

for item in ["All", "english", "german", "italian", "spanish,english", "french", "portuguese", "english,french", "french,english", "hawaiian,english", "spanish", "none"]:
    language_listbox.insert(tk.END, item)
    
# Apply filters button and Home button
filter_button = tk.Button(frame_filters, text="Apply Filters",font=("Helvetica", 10, 'bold'), command=filter_tabdb_data)
filter_button.grid(row=8, column=0, columnspan=2, pady=10)
apply_hover_effects(filter_button)

row_count_label = tk.Label(frame_filters, text="Number of Rows: 0",font=("Helvetica", 10, 'bold'))
row_count_label.grid(row=9, column=0, columnspan=2, pady=5)

# Sorting frame
tk.Label(frame_filters, text="Sort Column:",font=("Helvetica", 10, 'bold')).grid(row=8, column=2, padx=(20, 5))
sort_column_combo = ttk.Combobox(frame_filters, values=["Select Column"], state="readonly")
sort_column_combo.grid(row=8, column=3, padx=5)
sort_column_combo.set("Select Column")

sort_ascending_button = tk.Button(frame_filters, text="Sort Ascending",font=("Helvetica", 10, 'bold'), command=lambda: sort_filtered_data("Ascending"))
sort_descending_button = tk.Button(frame_filters, text="Sort Descending",font=("Helvetica", 10, 'bold'), command=lambda: sort_filtered_data("Descending"))
sort_ascending_button.grid(row=9, column=2, pady=5, padx=(20, 5))
sort_descending_button.grid(row=9, column=3, pady=5, padx=5)

apply_hover_effects(sort_ascending_button)
apply_hover_effects(sort_descending_button)

# Create style for the Treeview
style = ttk.Style()
style.configure("Treeview", rowheight=30, font=("Helvetica", 10, 'bold'))  # Set row height and font to bold
style.configure("Treeview.Heading", font=("Helvetica", 10, 'bold'))  # Set heading font to bold

# Create a frame to hold the Treeview and the scrollbars
table_frame = tk.Frame(main_frame)
table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Create the Treeview (output table)
tree = ttk.Treeview(table_frame, show="headings")
tree["columns"] = ["Column1", "Column2", "Column3"]  # Example column names
for col in tree["columns"]:
    tree.heading(col, text=col)
    tree.column(col, anchor="center", width=100)

# Add vertical scrollbar
scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
scrollbar_y.grid(row=0, column=1, sticky="ns")  # Place it on the right

# Add horizontal scrollbar
scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
scrollbar_x.grid(row=1, column=0, sticky="ew")  # Place it below the Treeview

# Configure the Treeview to use scrollbars
tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

# Place the Treeview in the grid
tree.grid(row=0, column=0, sticky="nsew")  # Fill the available space

# Configure row and column weights to ensure resizing works
table_frame.grid_rowconfigure(0, weight=1)
table_frame.grid_columnconfigure(0, weight=1)

# Plot Selection Frame (Plot Graphs Page)
plot_selection_frame = tk.Frame(app)

# Create a new frame to hold the Home and Previous buttons side by side
navigation_frame = tk.Frame(plot_selection_frame, bg="#264653")
navigation_frame.pack(anchor='nw', padx=10, pady=10)

# "Home" Button on plot_selection_frame
home_button_plot_selection = tk.Button(navigation_frame, text="Home",font=("Helvetica", 10, 'bold'), command=show_welcome_frame, bg='#FFC107', fg='black',width=8)
home_button_plot_selection.grid(row=0, column=0, padx=5, pady=5)  # Place in the first column

# Apply hover effect using apply_hover_effects function
apply_hover_effects(home_button_plot_selection)

tk.Label(plot_selection_frame, text="Show Plot Selection", font=("Helvetica", 20,'bold')).pack(pady=10)

# Add "Previous" button to the plot selection frame
previous_button = tk.Button(navigation_frame, text="Previous",font=("Helvetica", 10, 'bold'), command=show_main_frame,width=8)
previous_button.grid(row=0, column=1, padx=5, pady=5)  # Place in the first column
apply_hover_effects(previous_button)

# Create a new frame to hold the plot buttons in two columns
plot_button_frame = tk.Frame(plot_selection_frame, bg="#264653")
plot_button_frame.pack(pady=10)

# List of plot button labels and commands
plot_buttons = [
    ("Histogram of Songs by Difficulty", "difficulty"),
    ("Histogram of Songs by Duration", "duration"),
    ("Bar Chart of Songs by Language", "language"),
    ("Bar Chart of Songs by Source", "source"),
    ("Bar Chart of Songs by Decade", "decade"),
    ("Cumulative Songs Played by Date", "date"),
    ("Pie Chart of Songs by Gender", "gender"),
]

# Arrange buttons in two columns
for i, (label, plot_type) in enumerate(plot_buttons):
    row = i // 4  # Determine the row (0, 1, 2, etc.)
    col = i % 4  # Determine the column (0 or 1)
    button = tk.Button(
        plot_button_frame,
        text=label,
        font=("Helvetica", 10, "bold"),
        command=lambda pt=plot_type: generate_plots(pt),
        width=30,
        bg="#F4A261",
        fg="white"
    )
    button.grid(row=row, column=col, padx=5, pady=5)  # Add padding between buttons
    apply_hover_effects(button)
    
# Adjust the "Save All Plots to PDF" button to be centered below the two columns
save_plots_button = tk.Button(
    plot_selection_frame,
    text="Save All Plots to PDF",
    font=("Helvetica", 10, "bold"),
    command=save_plots_to_pdf,
    width=30,
    bg="#F4A261",
    fg="white"
)
save_plots_button.pack(pady=7)
apply_hover_effects(save_plots_button)

# Button frame to hold Load, Show Plot Selection, Refresh buttons within button frame
button_frame = tk.Frame(main_frame)
button_frame.pack(pady=10)

# Load Data, Show Plot Selection, and Refresh buttons within button frame
# Create buttons in button_frame with hover effects

show_plot_selection_button = tk.Button(button_frame, text="Show Plot Selection",font=("Helvetica", 10, 'bold'), command=show_plot_selection_frame)
show_plot_selection_button.pack(fill=tk.X, pady=2)
apply_hover_effects(show_plot_selection_button)

refresh_button = tk.Button(button_frame, text="Refresh",font=("Helvetica", 10, 'bold'), command=refresh_data)
refresh_button.pack(fill=tk.X, pady=2)
apply_hover_effects(refresh_button)

# Home Button - Moving to the extreme left of page 2 (frame_filters)
home_button_main = tk.Button(button_frame, text="Home", font=("Helvetica", 10, 'bold'),command=show_welcome_frame)
home_button_main.pack(fill=tk.X, pady=2)
apply_hover_effects(home_button_main)

# Start with the Welcome Frame
show_welcome_frame()

app.mainloop()

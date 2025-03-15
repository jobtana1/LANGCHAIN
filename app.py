cat > app.py << 'EOF'
# superagi_gui.py
import streamlit as st
import os
import json
import time
import threading
import subprocess
import psutil
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import your SUPER AGI system
# Assuming your system is in goal_oriented_agents.py
from goal_oriented_agents import (
    Goal, Agent, AgentRole, AgentCoordinator, 
    LLMBackwardChainer, ExecutionResult,
    WebSearchTool, FileReaderTool, APIRequestTool
)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.goals = []
    st.session_state.agents = []
    st.session_state.coordinator = None
    st.session_state.results = {}
    st.session_state.log_messages = []
    st.session_state.processing = False
    st.session_state.process_pid = None
    st.session_state.start_time = None
    st.session_state.thinking = False

# Function to add a log message
def add_log(message: str):
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.log_messages.append(f"[{timestamp}] {message}")

# Function to initialize the system
def initialize_system():
    if st.session_state.initialized:
        return

    add_log("Initializing SUPER AGI system...")

    # Create tools
    web_search_tool = WebSearchTool()
    file_reader_tool = FileReaderTool()
    api_request_tool = APIRequestTool()

    # Create agents with different roles
    agents = [
        Agent(
            name="Dr. Genetica",
            role=AgentRole.GENETICIST,
            capabilities=["genetic analysis", "genomic sequencing", "mutation identification"],
            tools=[web_search_tool, api_request_tool]
        ),
        Agent(
            name="Dr. Therapo",
            role=AgentRole.MEDICAL_EXPERT,
            capabilities=["drug development", "treatment protocols", "medical research"],
            tools=[web_search_tool, file_reader_tool]
        ),
        Agent(
            name="Dr. Testo",
            role=AgentRole.CLINICIAN,
            capabilities=["clinical trials", "patient assessment", "treatment validation"],
            tools=[api_request_tool]
        ),
        Agent(
            name="Research Master",
            role=AgentRole.RESEARCHER,
            capabilities=["literature review", "data analysis", "hypothesis generation"],
            tools=[web_search_tool, file_reader_tool, api_request_tool]
        )
    ]

    # Create coordinator
    coordinator = AgentCoordinator()

    # Add agents to coordinator
    for agent in agents:
        coordinator.add_agent(agent)

    # Store in session state
    st.session_state.agents = agents
    st.session_state.coordinator = coordinator
    st.session_state.initialized = True

    add_log("System initialized with 4 agents and their tools")

# Function to kill running processes
def kill_process():
    if st.session_state.process_pid:
        try:
            # Try to kill the process
            process = psutil.Process(st.session_state.process_pid)
            for proc in process.children(recursive=True):
                proc.kill()
            process.kill()
            add_log(f"Process {st.session_state.process_pid} terminated")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            add_log("Process already terminated")

        # Reset process state
        st.session_state.process_pid = None
        st.session_state.processing = False
        st.session_state.thinking = False
        st.session_state.start_time = None

        return "Process terminated"
    else:
        return "No active process to terminate"

# Function to process a goal
def process_goal(goal_description: str, knowledge_base: Dict[str, List[str]]):
    if not st.session_state.initialized:
        initialize_system()

    st.session_state.processing = True
    st.session_state.thinking = True
    st.session_state.start_time = datetime.now()
    add_log(f"Processing goal: {goal_description}")

    # Create main goal
    main_goal = Goal(
        description=goal_description,
        priority=5
    )

    # Create backward chainer
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        add_log("Error: No OpenAI API key found. Please set it in your environment.")
        st.session_state.processing = False
        st.session_state.thinking = False
        return

    chainer = LLMBackwardChainer(api_key)

    # Run in a separate thread to not block the UI
    def background_processing():
        try:
            # Start a process for this task
            process = psutil.Process(os.getpid())
            st.session_state.process_pid = process.pid

            # Decompose the goal
            add_log("Decomposing goal into sub-goals...")
            sub_goals = chainer.decompose_goal(main_goal, knowledge_base)

            # Signal that thinking phase is complete
            st.session_state.thinking = False

            # Add goals to coordinator
            st.session_state.coordinator.add_goal(main_goal)
            for sub_goal in sub_goals:
                st.session_state.coordinator.add_goal(sub_goal)

            # Store goals in session state
            st.session_state.goals = [main_goal] + sub_goals

            # Assign goals to agents
            add_log("Assigning goals to specialized agents...")
            st.session_state.coordinator.assign_goals_to_agents()

            # Execute goals
            add_log("Executing goals with specialized agents...")
            st.session_state.coordinator.execute_all_goals()

            # Store results
            for goal in [main_goal] + sub_goals:
                result = goal.get_latest_result()
                if result:
                    st.session_state.results[goal.id] = {
                        "description": goal.description,
                        "status": goal.status.value,
                        "agent": goal.assigned_agent.name if goal.assigned_agent else "None",
                        "success": result.success,
                        "message": result.message,
                        "data": result.data
                    }

            add_log("Goal processing complete!")
        except Exception as e:
            add_log(f"Error processing goal: {str(e)}")
        finally:
            st.session_state.processing = False
            st.session_state.process_pid = None

    # Start background thread
    threading.Thread(target=background_processing).start()

# Function to get elapsed time
def get_elapsed_time():
    if st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        minutes, seconds = divmod(elapsed.seconds, 60)
        return f"{minutes}m {seconds}s"
    return "0m 0s"

# Function to display file uploader for images
def image_uploader():
    uploaded_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        # Display the image
        image_bytes = uploaded_file.getvalue()
        encoded = base64.b64encode(image_bytes).decode()
        st.markdown(f"<img src='data:image/png;base64,{encoded}' style='max-width:100%'>", unsafe_allow_html=True)

        # Store in session state
        if 'uploaded_images' not in st.session_state:
            st.session_state.uploaded_images = []

        st.session_state.uploaded_images.append({
            "name": uploaded_file.name,
            "data": encoded,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return True
    return False

# Main app
def main():
    st.set_page_config(
        page_title="SUPER AGI System",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #4CAF50;
        }
        .sub-header {
            font-size: 1.5rem;
            color: #2196F3;
        }
        .success-text {
            color: #4CAF50;
            font-weight: bold;
        }
        .failure-text {
            color: #F44336;
            font-weight: bold;
        }
        .thinking-indicator {
            color: #FFC107;
            font-weight: bold;
            animation: blinker 1s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0.5; }
        }
        .elapsed-time {
            color: #673AB7;
            font-weight: bold;
        }
        .kill-button {
            background-color: #F44336;
            color: white;
            font-weight: bold;
            border-radius: 5px;
            padding: 10px 20px;
        }
        .code-block {
            background-color: #f5f5f5;
            border-radius: 5px;
            padding: 10px;
            border-left: 5px solid #2196F3;
            position: relative;
        }
        .copy-button {
            position: absolute;
            top: 5px;
            right: 5px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 5px 10px;
            cursor: pointer;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="main-header">SUPER AGI System</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Goal-Oriented Agents with Backward Chaining</p>', unsafe_allow_html=True)

    # Sidebar for system control
    with st.sidebar:
        st.header("System Control")
        if st.button("Initialize System"):
            initialize_system()

        # Process control section
        st.header("Process Control")

        # Display status and elapsed time
        if st.session_state.processing:
            if st.session_state.thinking:
                st.markdown('<p class="thinking-indicator">Thinking...</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="success-text">Processing</p>', unsafe_allow_html=True)

            st.markdown(f'<p class="elapsed-time">Elapsed time: {get_elapsed_time()}</p>', unsafe_allow_html=True)

            # Kill button
            if st.button("Kill Process", key="kill_button"):
                result = kill_process()
                st.write(result)
        else:
            st.write("No active process")

        # Settings section
        st.header("Settings")
        api_key = st.text_input("OpenAI API Key", type="password", 
                               value=os.environ.get("OPENAI_API_KEY", ""))
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            add_log("API key updated")

        # Image upload section
        st.header("Image Upload")
        image_uploader()

    # Main area tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Goal Input", "Execution Results", "System Logs", "Code Snippets"])

    # Tab 1: Goal Input
    with tab1:
        st.header("Enter Your Goal")
        goal_description = st.text_area("Goal Description", 
                                       value="Research the latest treatments for AMD (Age-related Macular Degeneration)")

        # Knowledge base input
        st.subheader("Knowledge Base")
        st.write("Enter comma-separated values for each category:")

        col1, col2 = st.columns(2)
        with col1:
            diseases = st.text_input("Diseases", value="AMD, diabetic retinopathy, glaucoma")
            symptoms = st.text_input("Symptoms", value="vision loss, blurriness, distortion")
            treatments = st.text_input("Treatments", value="medication, laser therapy, surgery, stem cell therapy")

        with col2:
            research_methods = st.text_input("Research Methods", value="clinical trials, lab experiments, genetic analysis")
            causes = st.text_input("Causes", value="aging, genetics, smoking, high blood pressure")
            resources = st.text_input("Resources", value="labs, funding, researchers")

        # Build knowledge base
        knowledge_base = {
            "diseases": [item.strip() for item in diseases.split(",")],
            "symptoms": [item.strip() for item in symptoms.split(",")],
            "treatments": [item.strip() for item in treatments.split(",")],
            "research_methods": [item.strip() for item in research_methods.split(",")],
            "causes": [item.strip() for item in causes.split(",")],
            "resources": [item.strip() for item in resources.split(",")]
        }

        # Process button
        if st.button("Process Goal", disabled=st.session_state.processing):
            process_goal(goal_description, knowledge_base)

        # Processing indicator
        if st.session_state.processing:
            status_text = "Thinking..." if st.session_state.thinking else "Processing goal..."
            st.info(f"{status_text} Elapsed time: {get_elapsed_time()}")
            progress_bar = st.progress(0)

            # This will be updated by a background thread
            def update_progress():
                progress = 0
                while st.session_state.processing and progress < 100:
                    # Simulate progress (in a real app, this would reflect actual progress)
                    time.sleep(0.1)
                    if st.session_state.thinking:
                        # Pulse between 0-30% during thinking phase
                        progress = (progress + 1) % 30
                    else:
                        # Steady progress during execution phase
                        progress = min(progress + 1, 99)
                    progress_bar.progress(progress)

            threading.Thread(target=update_progress, daemon=True).start()

    # Tab 2: Execution Results
    with tab2:
        st.header("Goal Execution Results")

        if not st.session_state.goals:
            st.info("No goals processed yet. Enter a goal in the 'Goal Input' tab.")
        else:
            # Main goal
            main_goal = st.session_state.goals[0]
            st.subheader(f"Main Goal: {main_goal.description}")

            # Main goal status
            status_color = {
                "pending": "🟡",
                "in_progress": "🔵",
                "completed": "🟢",
                "failed": "🔴"
            }

            st.write(f"Status: {status_color.get(main_goal.status.value, '⚪')} {main_goal.status.value.upper()}")

            if main_goal.id in st.session_state.results:
                result = st.session_state.results[main_goal.id]
                st.write(f"Result: {'✅ Success' if result['success'] else '❌ Failed'}")
                st.write(f"Message: {result['message']}")

                # Display data if available
                if result['data'] and 'execution_results' in result['data']:
                    with st.expander("Execution Details"):
                        for step_result in result['data']['execution_results']:
                            st.write(f"Step {step_result['step']}: {step_result['description']}")
                            st.json(step_result['result'])

            # Sub-goals
            st.subheader("Sub-Goals")
            for sub_goal in st.session_state.goals[1:]:
                with st.expander(f"{sub_goal.description} - {status_color.get(sub_goal.status.value, '⚪')} {sub_goal.status.value.upper()}"):
                    st.write(f"Assigned to: {sub_goal.assigned_agent.name if sub_goal.assigned_agent else 'None'}")

                    if sub_goal.id in st.session_state.results:
                        result = st.session_state.results[sub_goal.id]
                        st.write(f"Result: {'✅ Success' if result['success'] else '❌ Failed'}")
                        st.write(f"Message: {result['message']}")

                        # Display data if available
                        if result['data'] and 'execution_results' in result['data']:
                            st.write("Execution Steps:")
                            for step_result in result['data']['execution_results']:
                                st.write(f"- Step {step_result['step']}: {step_result['description']}")
                                with st.expander("Step Details"):
                                    st.json(step_result['result'])

    # Tab 3: System Logs
    with tab3:
        st.header("System Logs")

        # Log controls
        col1, col2 = st.columns([3, 1])
        with col1:
            auto_scroll = st.checkbox("Auto-scroll to latest logs", value=True)
        with col2:
            if st.button("Clear Logs"):
                st.session_state.log_messages = []

        # Display logs
        log_container = st.container()
        with log_container:
            for log in st.session_state.log_messages:
                st.text(log)

    # Tab 4: Code Snippets
    with tab4:
        st.header("Useful Code Snippets")

        # Code snippet 1: Kill Process
        st.subheader("Kill Process Command")
        code = "pkill -f 'python start.py'"
        st.markdown(f"""
        <div class="code-block">
            <pre>{code}</pre>
            <button class="copy-button" onclick="navigator.clipboard.writeText(`{code}`)">Copy</button>
        </div>
        """, unsafe_allow_html=True)

        # Code snippet 2: Run focused implementation
        st.subheader("Run Focused Implementation")
        code = "cd ~/superagi && python focused_start.py"
        st.markdown(f"""
        <div class="code-block">
            <pre>{code}</pre>
            <button class="copy-button" onclick="navigator.clipboard.writeText(`{code}`)">Copy</button>
        </div>
        """, unsafe_allow_html=True)

        # Code snippet 3: Check results
        st.subheader("Check Results")
        code = "cat ~/superagi/backward_chaining_implementation.py"
        st.markdown(f"""
        <div class="code-block">
            <pre>{code}</pre>
            <button class="copy-button" onclick="navigator.clipboard.writeText(`{code}`)">Copy</button>
        </div>
        """, unsafe_allow_html=True)

        # Add a button to execute the command directly
        if st.button("Execute Kill Command"):
            result = subprocess.run(["pkill", "-f", "python start.py"], capture_output=True, text=True)
            st.write("Command executed")
            if result.stdout:
                st.write(f"Output: {result.stdout}")
            if result.stderr:
                st.write(f"Error: {result.stderr}")

if __name__ == "__main__":
    main()
EOF

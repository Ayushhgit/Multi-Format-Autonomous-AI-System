document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('file');
    const processingStatus = document.getElementById('processingStatus');
    const results = document.getElementById('results');
    const resultContent = document.getElementById('resultContent');
    const error = document.getElementById('error');
    const tracesList = document.getElementById('tracesList');
    const tracesDropdownButton = document.getElementById('tracesDropdownButton');
    const tracesDropdownContent = document.getElementById('tracesDropdownContent');
    const dropdownIcon = document.getElementById('dropdownIcon');
    const fileNameSpan = document.getElementById('fileName');
    const resultsSection = document.getElementById('results');
    const controlsColumn = document.getElementById('controlsColumn');
    const mainContent = document.getElementById('mainContent');

    // Load recent traces
    loadTraces();

    // Handle file selection
    fileInput.addEventListener('change', (e) => {
        const fileName = e.target.files[0]?.name;
        if (fileName) {
            fileNameSpan.textContent = fileName;
        } else {
            fileNameSpan.textContent = 'Drag & Drop or Click to Upload';
        }
    });

    // Handle form submission
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select a file');
            return;
        }

        // Show processing status
        showProcessing();
        
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (response.ok) {
                showResults(data);
                loadTraces(); // Refresh traces list
            } else {
                showError(data.detail || 'An error occurred');
            }
        } catch (err) {
            showError('Failed to process file');
        } finally {
            hideProcessing();
        }
    });

    // Helper functions
    function showProcessing() {
        // Adjust layout for results
        controlsColumn.classList.remove('md:mx-auto', 'md:max-w-md', 'w-full');
        controlsColumn.classList.add('md:col-span-1', 'md:w-auto');
        mainContent.classList.add('md:grid-cols-3');
        resultsSection.classList.remove('hidden');

        processingStatus.classList.remove('hidden');
        results.classList.add('hidden'); // Hide previous results while processing
        error.classList.add('hidden');
    }

    function hideProcessing() {
        processingStatus.classList.add('hidden');
    }

    function showError(message) {
        // Adjust layout back if no results shown
        if (resultsSection.classList.contains('hidden')) {
            controlsColumn.classList.add('md:mx-auto', 'md:max-w-md', 'w-full');
            controlsColumn.classList.remove('md:col-span-1', 'md:w-auto');
            mainContent.classList.remove('md:grid-cols-3');
        }
        
        error.textContent = message;
        error.classList.remove('hidden');
        resultsSection.classList.add('hidden');
    }

    function showResults(data) {
        resultContent.innerHTML = formatResults(data);
        resultsSection.classList.remove('hidden');
        error.classList.add('hidden');
    }

    function formatResults(data) {
        const agentOutput = data.agent_output;
        let agentOutputHtml = '';

        // Section 2: Agent Output based on routing
        if (agentOutput && agentOutput.agent_type) {
             const agentType = agentOutput.agent_type.replace('enhanced_', '').toUpperCase() + ' Agent'; // Make agent type clearer

            if (agentOutput.agent_type === 'enhanced_json') {
                // Display output for EnhancedJSONAgent (raw JSON)
                 agentOutputHtml = `
                     <h3 class="font-semibold text-gray-700 mb-2">Output from ${agentType}</h3>
                     <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 max-h-96 overflow-auto">
                         <pre class="text-sm whitespace-pre-wrap">${JSON.stringify(agentOutput, null, 2)}</pre>
                     </div>
                 `;
            } else {
                // Default behavior for other agent types (show full JSON)
                 agentOutputHtml = `
                     <h3 class="font-semibold text-gray-700 mb-2">Output from ${agentType}</h3>
                     <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 max-h-96 overflow-auto">
                         <pre class="text-sm whitespace-pre-wrap">${JSON.stringify(agentOutput, null, 2)}</pre>
                     </div>
                 `;
            }
        } else {
            agentOutputHtml = `<p class="text-gray-600">No agent output available.</p>`;
        }

        return `
            <div class="space-y-6">
                 <div class="grid grid-cols-2 gap-4">
                     <div>
                         <h3 class="font-semibold text-gray-700 mb-1">Initial Classification (Routed Format)</h3>
                         <p class="text-gray-600">${data.format}</p>
                     </div>
                     <div>
                         <h3 class="font-semibold text-gray-700 mb-1">Initial Classification (Routed Intent)</h3>
                         <p class="text-gray-600">${data.intent}</p>
                     </div>
                 </div>
                
                 <div>
                     ${agentOutputHtml}
                 </div>
                
                 <div>
                     <h3 class="font-semibold text-gray-700 mb-2">Actions Taken (Routed Endpoints)</h3>
                     <div class="space-y-2 max-h-64 overflow-y-auto">
                          ${data.actions_taken.map(action => `
                              <div class="bg-gray-50 p-3 rounded-lg border border-gray-200">
                                  <p class="font-medium text-sm">Action Type: ${action.action.type}</p>
                                  <p class="text-sm text-gray-600">Status: ${action.status}</p>
                              </div>
                          `).join('')}
                      </div>
                  </div>
             </div>
         `;
    }

    async function loadTraces() {
        try {
            const response = await fetch('/traces');
            const data = await response.json();
            
            // Clear existing list items
            tracesList.innerHTML = '';

            if (data.traces && data.traces.length > 0) {
                tracesList.innerHTML = data.traces.map(trace => `
                    <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900" role="menuitem" 
                       onclick="loadTrace('${trace.trace_id}'); return false;">
                        <div class="flex justify-between items-center">
                            <div>
                                <p class="font-medium">${trace.format || 'Unknown Format'}</p>
                                <p class="text-xs text-gray-500">${new Date(trace.updated_at).toLocaleString()}</p>
                            </div>
                            <span class="px-2 py-1 text-xs rounded-full ${trace.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                ${trace.status || 'unknown'}
                            </span>
                        </div>
                    </a>
                `).join('');
            } else {
                tracesList.innerHTML = '<span class="block px-4 py-2 text-sm text-gray-500">No recent traces</span>';
            }
        } catch (err) {
            console.error('Failed to load traces:', err);
            tracesList.innerHTML = '<span class="block px-4 py-2 text-sm text-red-500">Error loading traces</span>';
        }
    }

    // Make loadTrace available globally
    window.loadTrace = async (traceId) => {
        try {
            // Highlight selected trace
            const traceItems = tracesList.querySelectorAll('a');
            traceItems.forEach(item => {
                item.classList.remove('bg-gray-200');
            });
            const selectedItem = tracesList.querySelector(`a[onclick*="loadTrace(\'${traceId}')"]`);
            if (selectedItem) {
                selectedItem.classList.add('bg-gray-200');
            }

            const response = await fetch(`/trace/${traceId}`);
            const data = await response.json();
            showResults(data.trace_data);
            tracesDropdownContent.classList.add('hidden'); // Close dropdown on selection
            dropdownIcon.classList.remove('rotate-180');
        } catch (err) {
            showError('Failed to load trace details');
        }
    };
});

// Handle dropdown toggle
tracesDropdownButton.addEventListener('click', () => {
    const isHidden = tracesDropdownContent.classList.contains('hidden');
    if (isHidden) {
        tracesDropdownContent.classList.remove('hidden');
        dropdownIcon.classList.add('rotate-180');
    } else {
        tracesDropdownContent.classList.add('hidden');
        dropdownIcon.classList.remove('rotate-180');
    }
});

document.addEventListener('click', (event) => {
    if (!tracesDropdownButton.contains(event.target) && !tracesDropdownContent.contains(event.target)) {
        tracesDropdownContent.classList.add('hidden');
        dropdownIcon.classList.remove('rotate-180');
    }
});
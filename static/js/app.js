/**
 * Soy Lunita - Infinite Tree Tasks
 * Frontend Application for Local-First To-Do Service
 * Aurora Theme Edition
 */

// ============================================
// Configuration & Constants
// ============================================
const API_BASE = '/api/v1';
// Use wss:// when the page is served over HTTPS (e.g. behind a reverse proxy)
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/ws`;

const STATUS_LABELS = {
  active: 'Active',
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
  deferred: 'Deferred',
  deleted: 'Deleted'
};

const PRIORITY_LABELS = {
  1: '🔴 Urgent',
  2: '🟠 High',
  3: '🟡 Medium',
  4: '🔵 Low'
};

// Animation durations (ms)
const ANIMATION = {
  fast: 150,
  normal: 300,
  slow: 500,
  stagger: 50
};

// ============================================
// State Management
// ============================================

// LocalStorage keys
const STORAGE_KEYS = {
  EXPANDED_TASKS: 'lunita_expanded_tasks',
  CURRENT_FILTER: 'lunita_current_filter'
};

// Load expanded tasks from localStorage
function loadExpandedTasksFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.EXPANDED_TASKS);
    if (stored) {
      const parsed = JSON.parse(stored);
      return new Set(parsed);
    }
  } catch (e) {
    console.warn('Failed to load expanded tasks from storage:', e);
  }
  return new Set();
}

// Save expanded tasks to localStorage
function saveExpandedTasksToStorage() {
  try {
    const expanded = Array.from(state.expandedTasks);
    localStorage.setItem(STORAGE_KEYS.EXPANDED_TASKS, JSON.stringify(expanded));
  } catch (e) {
    console.warn('Failed to save expanded tasks to storage:', e);
  }
}

// Load current filter from localStorage
function loadFilterFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.CURRENT_FILTER);
    if (stored) {
      // Validate that the filter is a known value
      const validFilters = ['all', 'active', 'completed', 'pending', 'in_progress', 'deferred'];
      if (validFilters.includes(stored)) {
        return stored;
      }
    }
  } catch (e) {
    console.warn('Failed to load filter from storage:', e);
  }
  return 'all';
}

// Save current filter to localStorage
function saveFilterToStorage() {
  try {
    localStorage.setItem(STORAGE_KEYS.CURRENT_FILTER, state.currentFilter);
  } catch (e) {
    console.warn('Failed to save filter to storage:', e);
  }
}

const state = {
  tasks: new Map(),          // id -> task object
  taskTree: [],              // root-level task IDs with hierarchy
  expandedTasks: loadExpandedTasksFromStorage(),  // expanded task IDs (loaded from storage)
  selectedTaskId: null,      // currently selected task
  currentFilter: loadFilterFromStorage(),  // current filter (loaded from storage)
  searchQuery: '',           // current search query
  visibleTaskIds: null,      // Set of task IDs visible under current filter (null = all visible)
  ws: null,                  // WebSocket connection
  wsConnected: false,
  undoEnabled: false,
  redoEnabled: false,
  draggedId: null,
  dropTarget: null,
  isLoading: true,
  lastCreatedTaskId: null,
  isLocalAction: false       // flag to prevent WebSocket double-renders
};

// Preload a transparent image for drag preview (hides default browser ghost)
const transparentDragImage = new Image();
transparentDragImage.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

// ============================================
// Utility Functions
// ============================================
function formatDate(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const taskDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (taskDate < today) {
    return 'Overdue';
  } else if (taskDate.getTime() === today.getTime()) {
    return 'Today';
  } else if (taskDate.getTime() === tomorrow.getTime()) {
    return 'Tomorrow';
  } else {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function isOverdue(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date();
}

function isToday(dateStr) {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const today = new Date();
  return date.toDateString() === today.toDateString();
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Initialize Lucide icons, scoped to a container when provided.
 * Scoping avoids rescanning the entire document on every partial render.
 */
function refreshIcons(root) {
  if (typeof lucide === 'undefined') return;
  lucide.createIcons(root ? { root } : undefined);
}

// ============================================
// Korean Markdown Bold Span Fixer
// ============================================
/**
 * Fix Markdown bold spans where Korean particles/endings appear after closing **.
 * 
 * Transforms patterns like:
 *   **내용**으로  →  **내용으로**
 *   **"경계선"**이야  →  **"경계선"이야**
 * 
 * The transformation moves Korean suffixes (particles, endings) that immediately
 * follow a closing ** inside the bold span, which fixes rendering in Markdown parsers.
 * 
 * Algorithm: O(n) single-pass state machine that tracks:
 * - Fenced code blocks (``` or ~~~)
 * - Inline code spans (backticks with matching counts)
 * - Bold markers (**)
 * 
 * @param {string} text - Input Markdown text
 * @returns {string} Text with Korean suffixes moved inside bold spans
 */
function fixKoreanBoldSpans(text) {
  if (!text) return text;

  /**
   * Check if a character can be part of a Korean suffix.
   * Includes Hangul syllables (가-힣) and Compatibility Jamo (ㄱ-ㅎ, ㅏ-ㅣ).
   */
  function isKoreanSuffixChar(c) {
    const code = c.charCodeAt(0);
    // Hangul syllables (가-힣): U+AC00 to U+D7A3
    if (code >= 0xAC00 && code <= 0xD7A3) return true;
    // Hangul Compatibility Jamo (ㄱ-ㅎ, ㅏ-ㅣ, etc.): U+3130 to U+318F
    if (code >= 0x3130 && code <= 0x318F) return true;
    return false;
  }

  // Punctuation that can follow a Korean suffix and should be absorbed
  const ABSORBABLE_PUNCTUATION = new Set([',', '.', '!', '?', '…', ';', ':']);

  // Opening punctuation that indicates the following ** is likely an opening marker
  const OPENING_CONTEXT_CHARS = new Set(['(', '[', '{']);

  /**
   * Extract a Korean suffix starting at the given position.
   * Returns the suffix (Korean chars + optional trailing punctuation) or empty string.
   */
  function extractKoreanSuffix(text, start) {
    let i = start;
    const n = text.length;

    // Collect Korean characters
    while (i < n && isKoreanSuffixChar(text[i])) {
      i++;
    }

    // Only include trailing punctuation if we found Korean characters
    if (i > start) {
      while (i < n && ABSORBABLE_PUNCTUATION.has(text[i])) {
        i++;
      }
    }

    return text.slice(start, i);
  }

  const result = [];
  let i = 0;
  const n = text.length;

  // State tracking for code contexts
  let inFencedCode = false;
  let fenceChar = '';
  let fenceLength = 0;

  let inInlineCode = false;
  let inlineBacktickCount = 0;

  while (i < n) {
    // ----------------------------------------------------------------
    // Fenced code block detection (``` or ~~~)
    // ----------------------------------------------------------------
    const atLineStart = (i === 0) || (text[i - 1] === '\n');

    if (atLineStart && !inInlineCode) {
      // Skip optional leading whitespace (up to 3 spaces per CommonMark)
      let wsEnd = i;
      while (wsEnd < n && (wsEnd - i) < 4 && (text[wsEnd] === ' ' || text[wsEnd] === '\t')) {
        wsEnd++;
      }

      // Check for fence marker (``` or ~~~)
      if (wsEnd < n && (text[wsEnd] === '`' || text[wsEnd] === '~')) {
        const fc = text[wsEnd];
        let fenceEnd = wsEnd;
        while (fenceEnd < n && text[fenceEnd] === fc) {
          fenceEnd++;
        }
        const fl = fenceEnd - wsEnd;

        if (fl >= 3) {
          if (!inFencedCode) {
            // Opening a fenced code block
            inFencedCode = true;
            fenceChar = fc;
            fenceLength = fl;
          } else if (fc === fenceChar && fl >= fenceLength) {
            // Closing the fenced code block
            inFencedCode = false;
            fenceChar = '';
            fenceLength = 0;
          }

          // Copy the entire line as-is
          let lineEnd = text.indexOf('\n', i);
          if (lineEnd === -1) {
            result.push(text.slice(i));
            i = n;
          } else {
            result.push(text.slice(i, lineEnd + 1));
            i = lineEnd + 1;
          }
          continue;
        }
      }
    }

    // If inside fenced code, copy character by character
    if (inFencedCode) {
      result.push(text[i]);
      i++;
      continue;
    }

    // ----------------------------------------------------------------
    // Inline code detection (backticks)
    // ----------------------------------------------------------------
    if (text[i] === '`') {
      const btStart = i;
      let btCount = 0;
      while (i < n && text[i] === '`') {
        btCount++;
        i++;
      }

      if (!inInlineCode) {
        // Opening inline code
        inInlineCode = true;
        inlineBacktickCount = btCount;
      } else if (btCount === inlineBacktickCount) {
        // Closing inline code (matching count)
        inInlineCode = false;
        inlineBacktickCount = 0;
      }
      // else: different count, these backticks are literal within code

      result.push(text.slice(btStart, i));
      continue;
    }

    // If inside inline code, just copy
    if (inInlineCode) {
      result.push(text[i]);
      i++;
      continue;
    }

    // ----------------------------------------------------------------
    // Bold marker detection (**)
    // ----------------------------------------------------------------
    if (i + 1 < n && text[i] === '*' && text[i + 1] === '*') {
      // Determine if this ** is potentially a closing marker
      let isPotentialClosing = false;
      if (result.length > 0) {
        const lastPiece = result[result.length - 1];
        if (lastPiece && lastPiece.length > 0) {
          const lastChar = lastPiece[lastPiece.length - 1];
          if (!/[\s]/.test(lastChar) && !OPENING_CONTEXT_CHARS.has(lastChar)) {
            isPotentialClosing = true;
          }
        }
      }

      // Look for Korean suffix immediately after the **
      const suffix = extractKoreanSuffix(text, i + 2);

      if (isPotentialClosing && suffix) {
        // Absorb the suffix into the bold span:
        // Output: [suffix][**] instead of [**][suffix]
        result.push(suffix);
        result.push('**');
        i += 2 + suffix.length;
      } else {
        // No suffix to absorb, just copy the **
        result.push('**');
        i += 2;
      }
      continue;
    }

    // ----------------------------------------------------------------
    // Default: copy character
    // ----------------------------------------------------------------
    result.push(text[i]);
    i++;
  }

  return result.join('');
}

// Smooth scroll to element
function scrollToElement(element, options = {}) {
  const { behavior = 'smooth', block = 'center' } = options;
  element.scrollIntoView({ behavior, block });
}

// ============================================
// API Functions
// ============================================
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      // FastAPI may return detail as an RFC 7807-style object; avoid "[object Object]"
      const detail = typeof error.detail === 'string'
        ? error.detail
        : error.detail?.detail || error.detail?.title || 'Request failed';
      throw new Error(detail);
    }

    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error(`API Error (${endpoint}):`, error);
    throw error;
  }
}

// Tasks API
async function fetchAllTasks() {
  return apiRequest('/tasks/');
}

async function fetchRootTasks(orderBy = 'custom') {
  return apiRequest(`/tasks/root?order_by=${orderBy}`);
}

async function fetchTaskChildren(taskId) {
  return apiRequest(`/tasks/${taskId}/children?order_by=custom`);
}

async function fetchTaskTree(orderBy = 'custom') {
  return apiRequest(`/tasks/tree?order_by=${orderBy}`);
}

async function createTask(taskData) {
  return apiRequest('/tasks/', {
    method: 'POST',
    body: JSON.stringify(taskData)
  });
}

async function updateTask(taskId, taskData) {
  return apiRequest(`/tasks/${taskId}`, {
    method: 'PUT',
    body: JSON.stringify(taskData)
  });
}

async function deleteTask(taskId, hard = false) {
  return apiRequest(`/tasks/${taskId}?hard_delete=${hard}`, {
    method: 'DELETE'
  });
}

async function moveTask(taskId, newParentId, position) {
  return apiRequest(`/tasks/${taskId}/move`, {
    method: 'PUT',
    body: JSON.stringify({ new_parent_id: newParentId, position })
  });
}

async function completeTaskTree(taskId, complete = true) {
  return apiRequest(`/tasks/${taskId}/complete-tree?complete=${complete}`, {
    method: 'POST'
  });
}

// Attachments API
async function fetchTaskAttachments(taskId) {
  return apiRequest(`/attachments/task/${taskId}`);
}

async function uploadAttachment(taskId, file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/attachments/upload/${taskId}`, {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

async function deleteAttachment(attachmentId) {
  return apiRequest(`/attachments/${attachmentId}`, {
    method: 'DELETE'
  });
}

function getAttachmentDownloadUrl(attachmentId) {
  return `${API_BASE}/attachments/download/${attachmentId}`;
}

// Undo/Redo API
async function performUndo() {
  return apiRequest('/undo-redo/undo', { method: 'POST' });
}

async function performRedo() {
  return apiRequest('/undo-redo/redo', { method: 'POST' });
}

async function fetchUndoStatus() {
  return apiRequest('/undo-redo/status');
}

// ============================================
// WebSocket Connection
// ============================================
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;

function connectWebSocket() {
  // Guard against duplicate sockets: skip if one is already open or connecting
  if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  state.ws = new WebSocket(WS_URL);

  state.ws.onopen = () => {
    console.log('🔌 WebSocket connected');
    state.wsConnected = true;
    wsReconnectAttempts = 0;
    updateConnectionStatus(true);
  };

  state.ws.onclose = () => {
    console.log('🔌 WebSocket disconnected');
    state.wsConnected = false;
    updateConnectionStatus(false);

    // Reconnect with exponential backoff (3s, 6s, 12s, ... capped at 30s)
    const delay = Math.min(3000 * Math.pow(2, wsReconnectAttempts), 30000);
    wsReconnectAttempts++;
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(connectWebSocket, delay);
  };

  state.ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  state.ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleWebSocketMessage(message);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };
}

function handleWebSocketMessage(message) {
  switch (message.type) {
    case 'connected':
      console.log('✅ WebSocket: Connection confirmed');
      break;

    case 'ping':
      state.ws.send(JSON.stringify({ type: 'pong' }));
      break;

    case 'task_update':
      handleTaskUpdate(message.event, message.data);
      break;

    case 'reset_needed':
      // Server says our state is too stale - do a full resync
      loadTasks();
      break;

    default:
      console.log('WebSocket message:', message);
  }
}

function handleTaskUpdate(event, data) {
  // Skip if this is triggered by a local action (prevents double-render)
  if (state.isLocalAction) {
    updateUndoRedoStatus();
    return;
  }

  switch (event) {
    case 'created':
      // Only show toast and reload if this wasn't our own action
      loadTasks();
      break;

    case 'updated':
      if (state.tasks.has(data.id)) {
        loadTasks();
      }
      break;

    case 'deleted':
      // Full reload: descendants and parent childIds must be updated too,
      // and a partial Map removal would leave the tree inconsistent
      if (state.tasks.has(data.id)) {
        loadTasks();
      }
      break;

    case 'restored':
    case 'moved':
    case 'reordered':
    case 'undo':
    case 'redo':
      loadTasks();
      break;
  }

  updateUndoRedoStatus();
}

function updateConnectionStatus(connected) {
  const statusEl = document.getElementById('connection-status');
  if (statusEl) {
    statusEl.classList.toggle('connected', connected);
    statusEl.title = connected ? 'Connected' : 'Disconnected - Reconnecting...';
    statusEl.innerHTML = connected
      ? '<i data-lucide="wifi"></i>'
      : '<i data-lucide="wifi-off"></i>';
    refreshIcons(statusEl);
  }
}

// ============================================
// Task Tree Building & Loading
// ============================================
async function loadTasks() {
  try {
    showLoading(true);

    // Use the batch tree API to fetch all tasks with hierarchy in one request
    // This eliminates N+1 queries
    const treeResponse = await fetchTaskTree('custom');

    state.tasks.clear();

    // Process the tree recursively
    function processTreeNode(node, parentId = null) {
      state.tasks.set(node.id, {
        ...node,
        parentId: parentId,
        childIds: node.children ? node.children.map(c => c.id) : []
      });

      if (node.children && node.children.length > 0) {
        node.children.forEach(child => processTreeNode(child, node.id));
      }
    }

    // Process all root tasks
    treeResponse.tasks.forEach(rootTask => processTreeNode(rootTask, null));

    // Extract root task IDs in order
    state.taskTree = treeResponse.tasks.map(task => task.id);

    renderTaskTree();
    updateStats();
    updateUndoRedoStatus();

  } catch (error) {
    console.error('Failed to load tasks:', error);

    // Fallback to the old N+1 approach if tree API fails
    try {
      await loadTasksLegacy();
    } catch (fallbackError) {
      console.error('Fallback also failed:', fallbackError);
      showToast('Failed to load tasks', 'error');
    }
  } finally {
    showLoading(false);
    state.isLoading = false;
  }
}

// Legacy loading function (N+1 queries) - used as fallback
async function loadTasksLegacy() {
  const allTasks = await fetchAllTasks();

  state.tasks.clear();
  const taskParents = new Map();

  // First pass: store all tasks
  allTasks.forEach(task => {
    state.tasks.set(task.id, { ...task, children: [], childIds: [] });
  });

  // Build hierarchy
  const rootTaskIds = new Set(allTasks.map(t => t.id));

  for (const task of allTasks) {
    try {
      const children = await fetchTaskChildren(task.id);
      if (children && children.length > 0) {
        const taskData = state.tasks.get(task.id);
        taskData.childIds = children.map(c => c.id);

        children.forEach(child => {
          rootTaskIds.delete(child.id);
          taskParents.set(child.id, task.id);

          if (!state.tasks.has(child.id)) {
            state.tasks.set(child.id, { ...child, children: [], childIds: [] });
          }
        });
      }
    } catch (e) {
      // Ignore errors for tasks without children
    }
  }

  // Store parent references
  taskParents.forEach((parentId, childId) => {
    const task = state.tasks.get(childId);
    if (task) {
      task.parentId = parentId;
    }
  });

  // Get root tasks in their correct sort order from the backend
  try {
    const rootTasks = await fetchRootTasks('custom');
    state.taskTree = rootTasks.map(task => task.id);
  } catch (e) {
    // Fallback to inferred root set if ordering request fails
    console.warn('Failed to fetch root task order, using fallback:', e);
    state.taskTree = Array.from(rootTaskIds);
  }

  renderTaskTree();
  updateStats();
  updateUndoRedoStatus();
}

// ============================================
// Rendering Functions
// ============================================
function showLoading(show) {
  const loadingEl = document.getElementById('loading-state');
  if (loadingEl) {
    loadingEl.style.display = show ? 'flex' : 'none';
  }
}

function renderTaskTree() {
  const container = document.getElementById('todo-tree');
  if (!container) return;

  // Apply filters
  let visibleRootIds = state.taskTree;

  // Search filter
  if (state.searchQuery) {
    const query = state.searchQuery.toLowerCase();
    const directMatchIds = new Set(); // Tasks that directly match the search
    const visibleIds = new Set();     // All tasks that should be visible
    const descendantsProcessed = new Set(); // Memoization to avoid redundant traversals

    // Helper function to add all descendants of a task (with memoization)
    function addAllDescendants(taskId) {
      // Skip if already processed to avoid redundant work
      if (descendantsProcessed.has(taskId)) return;
      descendantsProcessed.add(taskId);

      const task = state.tasks.get(taskId);
      if (!task || task.status === 'deleted') return;

      if (task.childIds && task.childIds.length > 0) {
        for (const childId of task.childIds) {
          const child = state.tasks.get(childId);
          if (child && child.status !== 'deleted') {
            visibleIds.add(childId);
            addAllDescendants(childId); // Recursively add descendants
          }
        }
      }
    }

    // First pass: find all directly matching tasks - O(n)
    state.tasks.forEach((task, id) => {
      if (task.status !== 'deleted' &&
        (task.title.toLowerCase().includes(query) ||
          (task.description && task.description.toLowerCase().includes(query)))) {
        directMatchIds.add(id);
        visibleIds.add(id);
      }
    });

    // Second pass: for each matching task, add ancestors and descendants
    directMatchIds.forEach(id => {
      // Add all ancestors (to show the path to matching items)
      const task = state.tasks.get(id);
      let parentId = task?.parentId;
      while (parentId) {
        visibleIds.add(parentId);
        const parent = state.tasks.get(parentId);
        parentId = parent?.parentId;
      }

      // Add all descendants (sub-items of matching items) - memoized for O(n) total
      addAllDescendants(id);
    });

    // Set visibleTaskIds so child filtering works correctly
    state.visibleTaskIds = visibleIds;
    visibleRootIds = state.taskTree.filter(id => visibleIds.has(id));
  } else {
    // No search query - reset visible task IDs (null means all visible)
    state.visibleTaskIds = null;
  }

  // Status filter
  // When search is active, we need to INTERSECT with search results, not replace them

  if (state.currentFilter !== 'all') {
    // Determine which tasks to consider: only search-visible tasks if search is active
    const searchVisibleIds = state.visibleTaskIds; // null if no search, Set if search active

    // Special handling for 'active' filter:
    // Show tasks that are uncompleted OR have any uncompleted descendants
    if (state.currentFilter === 'active') {
      const filteredIds = new Set();
      const hasUncompletedMemo = new Map(); // Memoization for O(n) performance

      // Memoized function to check if task or any descendant is uncompleted
      function hasUncompletedInSubtree(taskId) {
        if (hasUncompletedMemo.has(taskId)) {
          return hasUncompletedMemo.get(taskId);
        }

        const task = state.tasks.get(taskId);
        if (!task || task.status === 'deleted') {
          hasUncompletedMemo.set(taskId, false);
          return false;
        }

        // Task itself is uncompleted (not 'completed')
        if (task.status !== 'completed') {
          hasUncompletedMemo.set(taskId, true);
          return true;
        }

        // Check children recursively. When search is active, only consider
        // search-visible descendants: an uncompleted child that is hidden by
        // the search must not keep its completed ancestor visible (it would
        // render as a dangling parent with no visible children).
        let result = false;
        if (task.childIds && task.childIds.length > 0) {
          for (const childId of task.childIds) {
            if (searchVisibleIds && !searchVisibleIds.has(childId)) continue;
            if (hasUncompletedInSubtree(childId)) {
              result = true;
              break;
            }
          }
        }

        hasUncompletedMemo.set(taskId, result);
        return result;
      }

      // Check tasks - only those visible from search if search is active
      const tasksToCheck = searchVisibleIds
        ? Array.from(searchVisibleIds)
        : Array.from(state.tasks.keys());

      tasksToCheck.forEach(id => {
        const task = state.tasks.get(id);
        if (task && task.status !== 'deleted' && hasUncompletedInSubtree(id)) {
          filteredIds.add(id);
        }
      });

      // Store for use in renderTaskItem
      state.visibleTaskIds = filteredIds;
      visibleRootIds = visibleRootIds.filter(id => filteredIds.has(id));

    } else {
      // Standard status-based filtering for other filters
      const filterStatuses = {
        'completed': ['completed'],
        'pending': ['pending'],
        'in_progress': ['in_progress'],
        'deferred': ['deferred']
      };

      const allowedStatuses = filterStatuses[state.currentFilter] || [];

      if (allowedStatuses.length > 0) {
        const filteredIds = new Set();

        // Check tasks - only those visible from search if search is active
        const tasksToCheck = searchVisibleIds
          ? Array.from(searchVisibleIds)
          : Array.from(state.tasks.keys());

        tasksToCheck.forEach(id => {
          const task = state.tasks.get(id);
          if (task && allowedStatuses.includes(task.status)) {
            filteredIds.add(id);
            // Add ancestors to maintain tree structure (only if they were search-visible or no search)
            let parentId = task.parentId;
            while (parentId) {
              // Only add ancestor if it was visible in search results (or no search active)
              if (!searchVisibleIds || searchVisibleIds.has(parentId)) {
                filteredIds.add(parentId);
              }
              const parent = state.tasks.get(parentId);
              parentId = parent?.parentId;
            }
          }
        });

        // Store for use in renderTaskItem
        state.visibleTaskIds = filteredIds;
        visibleRootIds = visibleRootIds.filter(id => filteredIds.has(id));
      }
    }
  }

  // Clear container
  container.innerHTML = '';

  // Empty state
  if (visibleRootIds.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="140" height="140" viewBox="0 0 140 140" fill="none">
            <circle cx="70" cy="70" r="60" stroke="currentColor" stroke-width="2" stroke-dasharray="10 5" opacity="0.3"/>
            <circle cx="70" cy="70" r="45" stroke="url(#gradient-aurora)" stroke-width="1.5" opacity="0.4"/>
            <path d="M50 65L65 80L90 55" stroke="url(#gradient-aurora)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3>${state.searchQuery ? 'No matching tasks' : 'Your task list is empty'}</h3>
        <p>${state.searchQuery ? 'Try a different search term' : 'Press N or click below to create your first task'}</p>
      </div>
    `;
    return;
  }

  // Render tasks with staggered animation
  visibleRootIds.forEach((taskId, index) => {
    const taskEl = renderTaskItem(taskId, 0, index);
    if (taskEl) {
      container.appendChild(taskEl);
    }
  });

  // Initialize Lucide icons (scoped to the tree container)
  refreshIcons(container);

  // Scroll to newly created task if exists
  if (state.lastCreatedTaskId) {
    setTimeout(() => {
      const newTaskEl = document.querySelector(`[data-task-id="${state.lastCreatedTaskId}"]`);
      if (newTaskEl) {
        scrollToElement(newTaskEl);
        newTaskEl.classList.add('selected');
        state.selectedTaskId = state.lastCreatedTaskId;
      }
      state.lastCreatedTaskId = null;
    }, ANIMATION.normal);
  }
}

function renderTaskItem(taskId, depth, index = 0) {
  const task = state.tasks.get(taskId);
  if (!task || task.status === 'deleted') return null;

  const isExpanded = state.expandedTasks.has(taskId);
  // Check for visible children under current filter
  const visibleChildIds = state.visibleTaskIds && task.childIds
    ? task.childIds.filter(childId => state.visibleTaskIds.has(childId))
    : task.childIds;
  const hasChildren = visibleChildIds && visibleChildIds.length > 0;
  const hasAnyChildren = task.childIds && task.childIds.length > 0; // For completion badge
  const isCompleted = task.status === 'completed';
  const isInProgress = task.status === 'in_progress';
  const isSelected = state.selectedTaskId === taskId;

  const wrapper = document.createElement('div');
  wrapper.className = 'todo-item-wrapper';
  wrapper.dataset.taskId = taskId;
  wrapper.style.setProperty('--item-index', index);

  const item = document.createElement('div');
  // Build class list with all status states
  let itemClasses = 'todo-item';
  if (isCompleted) itemClasses += ' completed';
  if (isInProgress) itemClasses += ' in-progress';
  if (isSelected) itemClasses += ' selected';
  item.className = itemClasses;
  item.style.setProperty('--depth', depth);
  item.dataset.depth = depth;
  item.dataset.taskId = taskId;
  item.draggable = true;

  // Build badges HTML
  let badges = '';

  // In Progress badge (FIRST - leftmost) - animated status indicator
  if (isInProgress) {
    badges += `
      <span class="in-progress-badge" title="Task is in progress">
        <span class="badge-icon"><i data-lucide="loader-2"></i></span>
        <span class="badge-text">In Progress</span>
      </span>
    `;
  }

  // Due date badge - only show for non-completed tasks
  if (task.next_due_utc && !isCompleted) {
    const dueDateClass = isOverdue(task.next_due_utc) ? 'overdue' : (isToday(task.next_due_utc) ? 'today' : '');
    badges += `
      <span class="due-badge ${dueDateClass}" title="${formatDate(task.next_due_utc)}">
        <i data-lucide="calendar"></i>
        ${formatDateShort(task.next_due_utc)}
      </span>
    `;
  }

  // Completion badge for parents - shows overall stats regardless of filter
  if (hasAnyChildren && !isCompleted) {
    const { completed, total } = getCompletionStats(taskId);
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    badges += `
      <span class="completion-badge">
        <span class="completion-progress" style="width: ${percentage}%"></span>
        <span class="completion-text">${completed}/${total}</span>
      </span>
    `;
  }

  // Priority indicator (rightmost)
  if (task.priority && task.priority <= 4) {
    badges += `<span class="priority-indicator" data-priority="${task.priority}" title="${PRIORITY_LABELS[task.priority]}"></span>`;
  }

  item.innerHTML = `
    <div class="todo-content">
      ${hasChildren ? `
        <button class="expand-btn ${isExpanded ? 'expanded' : ''}" data-action="toggle-expand">
          <i data-lucide="chevron-right"></i>
        </button>
      ` : '<div class="expand-placeholder"></div>'}
      
      <button class="checkbox ${isCompleted ? 'checked' : ''}" data-action="toggle-complete">
        <i data-lucide="${isCompleted ? 'check-circle-2' : 'circle'}"></i>
      </button>
      
      <span class="todo-title" data-action="open-detail">${escapeHtml(task.title)}</span>
      
      <div class="todo-badges">${badges}</div>
      
      <div class="todo-actions">
        <button class="action-btn add-btn" data-action="add-subtask" title="Add subtask (+)">
          <i data-lucide="plus"></i>
        </button>
        <button class="action-btn delete-btn" data-action="delete" title="Delete">
          <i data-lucide="trash-2"></i>
        </button>
      </div>
    </div>
  `;

  // Event listeners
  item.addEventListener('click', (e) => handleTaskItemClick(e, taskId));
  item.addEventListener('dblclick', (e) => handleTaskItemDblClick(e, taskId));
  item.addEventListener('dragstart', (e) => handleDragStart(e, taskId));
  item.addEventListener('dragend', handleDragEnd);
  item.addEventListener('dragover', (e) => handleDragOver(e, taskId));
  item.addEventListener('drop', (e) => handleDrop(e, taskId));
  item.addEventListener('dragleave', handleDragLeave);

  wrapper.appendChild(item);

  // Render children (only those visible under current filter)
  if (hasChildren && isExpanded) {
    const childrenContainer = document.createElement('div');
    childrenContainer.className = 'todo-children';

    // Filter children based on visibility
    const visibleChildIds = state.visibleTaskIds
      ? task.childIds.filter(childId => state.visibleTaskIds.has(childId))
      : task.childIds;

    visibleChildIds.forEach((childId, childIndex) => {
      const childEl = renderTaskItem(childId, depth + 1, childIndex);
      if (childEl) {
        childrenContainer.appendChild(childEl);
      }
    });

    // Only append if there are visible children
    if (childrenContainer.children.length > 0) {
      wrapper.appendChild(childrenContainer);
    }
  }

  return wrapper;
}

function getCompletionStats(taskId) {
  let total = 0;
  let completed = 0;

  function countRecursive(id) {
    const task = state.tasks.get(id);
    if (!task || task.status === 'deleted') return;

    if (task.childIds && task.childIds.length > 0) {
      task.childIds.forEach(childId => {
        const child = state.tasks.get(childId);
        if (child && child.status !== 'deleted') {
          total++;
          if (child.status === 'completed') completed++;
          countRecursive(childId);
        }
      });
    }
  }

  countRecursive(taskId);
  return { total, completed };
}

// ============================================
// Task Item Event Handlers
// ============================================
function handleTaskItemClick(e, taskId) {
  const action = e.target.closest('[data-action]')?.dataset.action;

  switch (action) {
    case 'toggle-expand':
      toggleExpand(taskId);
      break;

    case 'toggle-complete':
      toggleComplete(taskId);
      break;

    case 'open-detail':
      openTaskModal(taskId);
      break;

    case 'add-subtask':
      e.stopPropagation();
      openCreateTaskModal(taskId);
      break;

    case 'delete':
      e.stopPropagation();
      confirmDeleteTask(taskId);
      break;

    default:
      selectTask(taskId);
  }
}

function handleTaskItemDblClick(e, taskId) {
  // Double-click on title opens the edit modal
  if (e.target.classList.contains('todo-title')) {
    openTaskModal(taskId);
    return;
  }

  // Double-click elsewhere toggles expand/collapse (if task has children)
  const task = state.tasks.get(taskId);
  if (task && task.childIds && task.childIds.length > 0) {
    toggleExpand(taskId);
  }
}

function selectTask(taskId) {
  state.selectedTaskId = taskId;

  // Update visual selection
  document.querySelectorAll('.todo-item.selected').forEach(el => {
    el.classList.remove('selected');
  });

  const taskEl = document.querySelector(`.todo-item[data-task-id="${taskId}"]`);
  if (taskEl) {
    taskEl.classList.add('selected');
  }
}

function clearSelection() {
  state.selectedTaskId = null;
  document.querySelectorAll('.todo-item.selected').forEach(el => {
    el.classList.remove('selected');
  });
}

function toggleExpand(taskId) {
  if (state.expandedTasks.has(taskId)) {
    state.expandedTasks.delete(taskId);
  } else {
    state.expandedTasks.add(taskId);
  }
  saveExpandedTasksToStorage();
  renderTaskTree();
}

async function toggleComplete(taskId) {
  const task = state.tasks.get(taskId);
  if (!task) return;

  const newStatus = task.status === 'completed' ? 'pending' : 'completed';
  const hasChildren = task.childIds && task.childIds.length > 0;
  const isCompleting = newStatus === 'completed';

  // Optimistic update for snappy feel
  task.status = newStatus;

  // If completing a parent task, also update children visually
  if (hasChildren && isCompleting) {
    const updateChildrenStatus = (parentId, status) => {
      const parent = state.tasks.get(parentId);
      if (parent && parent.childIds) {
        parent.childIds.forEach(childId => {
          const child = state.tasks.get(childId);
          if (child) {
            child.status = status;
            updateChildrenStatus(childId, status);
          }
        });
      }
    };
    updateChildrenStatus(taskId, newStatus);
  }

  renderTaskTree();

  try {
    state.isLocalAction = true;

    // Use cascade API for parent tasks when completing
    if (hasChildren && isCompleting) {
      await completeTaskTree(taskId, true);
      showToast('✓ Task and subtasks completed!', 'success');
    } else if (hasChildren && !isCompleting) {
      // When uncompleting a parent, only uncomplete the parent itself
      await updateTask(taskId, { status: newStatus });
      showToast('Task reopened', 'success');
    } else {
      await updateTask(taskId, { status: newStatus });
      showToast(newStatus === 'completed' ? '✓ Task completed!' : 'Task reopened', 'success');
    }

    // Reload to get accurate state
    await loadTasks();
    updateStats();
  } catch (error) {
    // Revert on error - reload to get correct state
    await loadTasks();
    showToast('Failed to update task', 'error');
  } finally {
    setTimeout(() => { state.isLocalAction = false; }, 500);
  }
}

async function confirmDeleteTask(taskId) {
  const task = state.tasks.get(taskId);
  if (!task) return;

  const hasChildren = task.childIds && task.childIds.length > 0;
  const message = hasChildren
    ? `This will delete "${task.title}" and all its subtasks.`
    : `This will delete "${task.title}".`;

  const confirmed = await showConfirm({
    title: 'Delete Task',
    message: message,
    confirmText: 'Delete',
    type: 'danger'
  });

  if (confirmed) {
    try {
      state.isLocalAction = true;
      await deleteTask(taskId);

      // Remove task and all descendants from local state
      const removeTaskAndDescendants = (id) => {
        const t = state.tasks.get(id);
        if (t && t.childIds) {
          t.childIds.forEach(childId => removeTaskAndDescendants(childId));
        }
        state.tasks.delete(id);
      };
      removeTaskAndDescendants(taskId);

      // Remove from parent's children or root
      if (task.parentId) {
        const parent = state.tasks.get(task.parentId);
        if (parent) {
          parent.childIds = parent.childIds.filter(id => id !== taskId);
        }
      } else {
        state.taskTree = state.taskTree.filter(id => id !== taskId);
      }

      renderTaskTree();
      updateStats();
      showToast(hasChildren ? 'Task and subtasks deleted' : 'Task deleted', 'success');
    } catch (error) {
      showToast('Failed to delete task', 'error');
    } finally {
      setTimeout(() => { state.isLocalAction = false; }, 500);
    }
  }
}

// ============================================
// Drag and Drop
// ============================================
function handleDragStart(e, taskId) {
  state.draggedId = taskId;
  e.target.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', taskId);

  // Use transparent image to hide the default browser drag ghost/icons
  e.dataTransfer.setDragImage(transparentDragImage, 0, 0);
}

function handleDragEnd(e) {
  state.draggedId = null;
  state.dropTarget = null;
  e.target.classList.remove('dragging');

  document.querySelectorAll('.todo-item.drop-target').forEach(el => {
    el.classList.remove('drop-target');
  });
  document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
}

function handleDragOver(e, targetId) {
  e.preventDefault();
  e.stopPropagation();

  // Always set dropEffect to show the correct cursor
  e.dataTransfer.dropEffect = 'move';

  // When dragging over self, just prevent default (for valid cursor) but don't show indicators
  if (state.draggedId === targetId) {
    // Clear any existing indicators but don't set as drop target
    document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
    document.querySelectorAll('.todo-item.drop-target').forEach(el => {
      el.classList.remove('drop-target');
    });
    state.dropTarget = null;
    return;
  }

  const rect = e.currentTarget.getBoundingClientRect();
  const y = e.clientY - rect.top;
  const height = rect.height;

  // Remove existing indicators
  document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
  document.querySelectorAll('.todo-item.drop-target').forEach(el => {
    el.classList.remove('drop-target');
  });

  let position = 'inside';
  if (y < height * 0.25) {
    position = 'before';
  } else if (y > height * 0.75) {
    position = 'after';
  }

  state.dropTarget = { id: targetId, position };

  const itemEl = e.currentTarget;

  if (position === 'inside') {
    itemEl.classList.add('drop-target');
  } else {
    const indicator = document.createElement('div');
    indicator.className = `drop-indicator drop-${position}`;
    itemEl.appendChild(indicator);
  }
}

function handleDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    e.currentTarget.classList.remove('drop-target');
    e.currentTarget.querySelectorAll('.drop-indicator').forEach(el => el.remove());
  }
}

async function handleDrop(e, targetId) {
  e.preventDefault();
  e.stopPropagation();

  if (!state.draggedId || !state.dropTarget) return;
  if (state.draggedId === targetId) return;

  const draggedTask = state.tasks.get(state.draggedId);
  const targetTask = state.tasks.get(targetId);

  if (!draggedTask || !targetTask) return;

  // Check if target is descendant of dragged
  if (isDescendant(targetId, state.draggedId)) {
    showToast('Cannot move a task into its own subtask', 'error');
    return;
  }

  try {
    state.isLocalAction = true;
    const { position } = state.dropTarget;

    if (position === 'inside') {
      await moveTask(state.draggedId, targetId, 0);
      // Auto-expand the target task to show the newly moved subtask
      state.expandedTasks.add(targetId);
      saveExpandedTasksToStorage();
    } else {
      const newParentId = targetTask.parentId || null;
      const siblings = newParentId
        ? state.tasks.get(newParentId)?.childIds || []
        : state.taskTree;

      let newPosition = siblings.indexOf(targetId);
      if (position === 'after') newPosition++;

      await moveTask(state.draggedId, newParentId, newPosition);
    }

    await loadTasks();
    showToast('Task moved', 'success');

  } catch (error) {
    showToast('Failed to move task', 'error');
  } finally {
    setTimeout(() => { state.isLocalAction = false; }, 500);
  }
}

function isDescendant(potentialDescendantId, ancestorId) {
  const ancestor = state.tasks.get(ancestorId);
  if (!ancestor || !ancestor.childIds) return false;

  for (const childId of ancestor.childIds) {
    if (childId === potentialDescendantId) return true;
    if (isDescendant(potentialDescendantId, childId)) return true;
  }

  return false;
}

// ============================================
// Task Modal (Create & Edit modes)
// ============================================
let currentModalTaskId = null;
let modalMode = 'edit'; // 'edit' or 'create'
let createTaskParentId = null;

// Track original values for dirty check
let originalModalValues = {
  title: '',
  status: '',
  priority: '',
  description: '',
  dueDate: ''
};

// Track mousedown target for proper modal close behavior
let modalMouseDownTarget = null;

// Description view/edit mode
let descriptionMode = 'edit'; // 'view' or 'edit'

/**
 * Configure marked.js options for safe rendering
 */
function initializeMarked() {
  if (typeof marked !== 'undefined') {
    // Configure marked with safe defaults
    marked.setOptions({
      breaks: true,       // Convert \n to <br>
      gfm: true,          // GitHub Flavored Markdown
      headerIds: false,   // Don't add IDs to headers (security)
      mangle: false       // Don't mangle email addresses
    });

    // Add custom renderer to escape raw HTML for XSS protection
    const renderer = {
      // Escape raw HTML blocks
      // Note: marked.js passes an object { raw, block, text }, use destructuring
      html({ text }) {
        return escapeHtml(text);
      },
    // Sanitize links to prevent javascript: URLs
    // Note: marked.js passes an object { href, title, text, tokens }, use destructuring
    link({ href, title, text }) {
      // Block dangerous URL schemes
      const lowerHref = (href || '').toLowerCase().trim();
      if (lowerHref.startsWith('javascript:') ||
        lowerHref.startsWith('vbscript:') ||
        lowerHref.startsWith('data:')) {
        return escapeHtml(text);
      }
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
      return `<a href="${escapeHtml(href)}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
    },
    // Sanitize images
    // Note: marked.js passes an object { href, title, text }, use destructuring
    image({ href, title, text }) {
      // Block dangerous URL schemes. data: URIs are only allowed for safe
      // raster image types - data:image/svg+xml can carry embedded scripts
      const lowerHref = (href || '').toLowerCase().trim();
      const isSafeDataUri = /^data:image\/(png|jpe?g|gif|webp);/.test(lowerHref);
      if (lowerHref.startsWith('javascript:') ||
        lowerHref.startsWith('vbscript:') ||
        (lowerHref.startsWith('data:') && !isSafeDataUri)) {
        return escapeHtml(text);
      }
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
      const altAttr = text ? ` alt="${escapeHtml(text)}"` : '';
      return `<img src="${escapeHtml(href)}"${altAttr}${titleAttr}>`;
    },
      // Custom checkbox renderer - INTERACTIVE (no disabled attribute)
      // Note: marked.js passes an object { checked: boolean }, use destructuring
      checkbox({ checked }) {
        return `<input type="checkbox" class="md-checkbox"${checked ? ' checked' : ''}>`;
      }
    };

    marked.use({ renderer });
  }
}

/**
 * Setup event delegation for markdown checkbox interactions
 * This allows checkboxes in rendered markdown to be clickable
 */
function setupMarkdownCheckboxHandler() {
  const descriptionView = document.getElementById('modal-description-view');
  if (!descriptionView) return;

  // Use 'change' event instead of 'click' - fires AFTER browser toggles the checkbox
  descriptionView.addEventListener('change', (e) => {
    if (e.target.matches('input[type="checkbox"].md-checkbox')) {
      // Browser has already toggled the checkbox, just sync to source
      syncMarkdownCheckboxToSource(descriptionView);
    }
  });
}

/**
 * Sync checkbox states from rendered view back to markdown source
 * @param {HTMLElement} viewElement - The description view container
 */
function syncMarkdownCheckboxToSource(viewElement) {
  const textarea = document.getElementById('modal-description');
  if (!textarea) return;

  let markdown = textarea.value;
  const checkboxes = viewElement.querySelectorAll('input[type="checkbox"].md-checkbox');

  // Track which checkbox we're on as we scan through the markdown
  let checkboxIndex = 0;

  // Replace task list items based on their order (supports both unordered and ordered lists)
  markdown = markdown.replace(/^(\s*(?:[-*+]|\d+[.)])\s*)\[([ xX])\]/gm, (match, prefix, state) => {
    if (checkboxIndex < checkboxes.length) {
      const isChecked = checkboxes[checkboxIndex].checked;
      checkboxIndex++;
      return `${prefix}[${isChecked ? 'x' : ' '}]`;
    }
    return match;
  });

  // Update textarea
  textarea.value = markdown;
}

/**
 * Smooth floating toggle button for the description view/edit control.
 * Uses lerp so the button glides to its target position instead of
 * snapping rigidly like position:sticky.
 *
 * Layout is cached once per modal open / mode switch. On each scroll
 * frame only modalBody.scrollTop is read — no getBoundingClientRect
 * in the hot path, no subtracting the live transform.
 */
const smoothStickyToggle = (() => {
  let currentY = 0;
  let targetY = 0;
  let animFrameId = null;
  let modalBody = null;
  let toggleBtn = null;
  let rightColumn = null;

  let layoutCached = false;
  let btnScrollY = 0;
  let maxTranslateY = Infinity;

  const LERP = 0.15;
  const TOP_MARGIN = 8;

  function cacheLayout() {
    if (!modalBody || !toggleBtn || !rightColumn) return;
    if (toggleBtn.offsetParent === null) return;

    toggleBtn.style.transform = '';
    currentY = 0;

    const bodyRect = modalBody.getBoundingClientRect();
    const btnRect = toggleBtn.getBoundingClientRect();
    const colRect = rightColumn.getBoundingClientRect();

    btnScrollY = btnRect.top - bodyRect.top + modalBody.scrollTop;
    maxTranslateY = colRect.bottom - btnRect.top - toggleBtn.offsetHeight - TOP_MARGIN;

    layoutCached = true;
  }

  function calculateTarget() {
    if (!layoutCached) cacheLayout();

    const scrollPast = modalBody.scrollTop + TOP_MARGIN - btnScrollY;

    if (scrollPast > 0) {
      targetY = Math.min(scrollPast, Math.max(0, maxTranslateY));
    } else {
      targetY = 0;
    }
  }

  function animate() {
    const diff = targetY - currentY;

    if (Math.abs(diff) < 0.5) {
      currentY = targetY;
    } else {
      currentY += diff * LERP;
    }

    toggleBtn.style.transform = currentY > 0.5
      ? `translateY(${Math.round(currentY * 10) / 10}px)`
      : '';

    if (Math.abs(targetY - currentY) > 0.5) {
      animFrameId = requestAnimationFrame(animate);
    } else {
      animFrameId = null;
    }
  }

  function onScroll() {
    calculateTarget();
    if (!animFrameId) {
      animFrameId = requestAnimationFrame(animate);
    }
  }

  return {
    init() {
      modalBody = document.querySelector('.modal-body');
      toggleBtn = document.getElementById('description-toggle-btn');
      rightColumn = document.querySelector('.modal-right-column');
      if (!modalBody || !toggleBtn || !rightColumn) return;

      modalBody.addEventListener('scroll', onScroll, { passive: true });
    },

    reset() {
      currentY = 0;
      targetY = 0;
      if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
      }
      if (toggleBtn) toggleBtn.style.transform = '';
      layoutCached = false;
    }
  };
})();

// Placeholder tokens to protect LaTeX from markdown processing
const LATEX_TOKENS = {
  INLINE_BLOCK_PREFIX: '\u0000LATEX_INLINE_',
  INLINE_BLOCK_SUFFIX: '_IEND\u0000',
  DISPLAY_BLOCK_PREFIX: '\u0000LATEX_BLOCK_',
  DISPLAY_BLOCK_SUFFIX: '_END\u0000'
};

/**
 * Extract display math blocks to avoid markdown line-break transforms
 * Supports $$...$$ and \[...\] with multiline content.
 * @param {string} text - The markdown text
 * @returns {{ text: string, blocks: Array<{ delimiter: string, content: string }> }}
 */
function extractDisplayMathBlocks(text) {
  if (!text) return { text, blocks: [] };

  const blocks = [];
  let index = 0;

  function replaceDisplayMath(segment) {
    let result = segment;

    // Extract \[...\] blocks
    result = result.replace(/\\\[[\s\S]*?\\\]/g, (match) => {
      const content = match.slice(2, -2);
      const token = `${LATEX_TOKENS.DISPLAY_BLOCK_PREFIX}${index}${LATEX_TOKENS.DISPLAY_BLOCK_SUFFIX}`;
      blocks.push({ delimiter: '\\[', content });
      index += 1;
      return token;
    });

    // Extract $$...$$ blocks
    result = result.replace(/\$\$[\s\S]*?\$\$/g, (match) => {
      const content = match.slice(2, -2);
      const token = `${LATEX_TOKENS.DISPLAY_BLOCK_PREFIX}${index}${LATEX_TOKENS.DISPLAY_BLOCK_SUFFIX}`;
      blocks.push({ delimiter: '$$', content });
      index += 1;
      return token;
    });

    return result;
  }

  function replaceDisplayMathOutsideInlineCode(segment) {
    const inlineCodeRegex = /`[^`\n]*`/g;
    let lastIndex = 0;
    let result = '';
    let match;

    while ((match = inlineCodeRegex.exec(segment))) {
      const before = segment.slice(lastIndex, match.index);
      result += replaceDisplayMath(before);
      result += match[0];
      lastIndex = inlineCodeRegex.lastIndex;
    }

    result += replaceDisplayMath(segment.slice(lastIndex));
    return result;
  }

  const fenceRegex = /```[\s\S]*?```/g;
  let lastIndex = 0;
  let match;
  let rebuilt = '';

  while ((match = fenceRegex.exec(text))) {
    const before = text.slice(lastIndex, match.index);
    rebuilt += replaceDisplayMathOutsideInlineCode(before);
    rebuilt += match[0];
    lastIndex = fenceRegex.lastIndex;
  }

  rebuilt += replaceDisplayMathOutsideInlineCode(text.slice(lastIndex));
  text = rebuilt;

  return { text, blocks };
}

/**
 * Restore display math blocks after markdown processing
 * @param {string} html - The rendered HTML
 * @param {Array<{ delimiter: string, content: string }>} blocks
 * @returns {string} HTML with restored display math blocks
 */
function restoreDisplayMathBlocks(html, blocks) {
  if (!html || !blocks.length) return html;

  return blocks.reduce((result, block, index) => {
    const token = `${LATEX_TOKENS.DISPLAY_BLOCK_PREFIX}${index}${LATEX_TOKENS.DISPLAY_BLOCK_SUFFIX}`;
    const trimmedContent = block.content.trim();
    const restored = block.delimiter === '\\['
      ? `\\[\n${trimmedContent}\n\\]`
      : `$$\n${trimmedContent}\n$$`;
    return result.replace(new RegExp(token, 'g'), restored);
  }, html);
}

/**
 * Extract inline math blocks \(...\) to protect the full expression
 * (delimiters AND content) from markdown processing.
 * Skips fenced code blocks and inline code spans.
 * @param {string} text - The markdown text
 * @returns {{ text: string, blocks: string[] }}
 */
function extractInlineMathBlocks(text) {
  if (!text) return { text, blocks: [] };

  const blocks = [];

  function replaceInlineMath(segment) {
    return segment.replace(/\\\([\s\S]*?\\\)/g, (match) => {
      const idx = blocks.length;
      blocks.push(match);
      return `${LATEX_TOKENS.INLINE_BLOCK_PREFIX}${idx}${LATEX_TOKENS.INLINE_BLOCK_SUFFIX}`;
    });
  }

  function replaceOutsideInlineCode(segment) {
    const inlineCodeRegex = /`[^`\n]*`/g;
    let lastIdx = 0;
    let result = '';
    let m;

    while ((m = inlineCodeRegex.exec(segment))) {
      result += replaceInlineMath(segment.slice(lastIdx, m.index));
      result += m[0];
      lastIdx = inlineCodeRegex.lastIndex;
    }

    result += replaceInlineMath(segment.slice(lastIdx));
    return result;
  }

  const fenceRegex = /```[\s\S]*?```/g;
  let lastIdx = 0;
  let m;
  let rebuilt = '';

  while ((m = fenceRegex.exec(text))) {
    rebuilt += replaceOutsideInlineCode(text.slice(lastIdx, m.index));
    rebuilt += m[0];
    lastIdx = fenceRegex.lastIndex;
  }

  rebuilt += replaceOutsideInlineCode(text.slice(lastIdx));
  return { text: rebuilt, blocks };
}

/**
 * Restore inline math blocks after markdown processing
 * @param {string} html - The rendered HTML
 * @param {string[]} blocks - The extracted inline math expressions
 * @returns {string} HTML with restored inline math
 */
function restoreInlineMathBlocks(html, blocks) {
  if (!html || !blocks.length) return html;

  return blocks.reduce((result, block, index) => {
    const token = `${LATEX_TOKENS.INLINE_BLOCK_PREFIX}${index}${LATEX_TOKENS.INLINE_BLOCK_SUFFIX}`;
    return result.replace(new RegExp(token, 'g'), block);
  }, html);
}

/**
 * Render markdown content to HTML
 * @param {string} markdown - The markdown content to render
 * @returns {string} HTML string
 */
function renderMarkdown(markdown) {
  if (!markdown || !markdown.trim()) {
    return '';
  }

  // Extract display math blocks before markdown processing
  const displayExtraction = extractDisplayMathBlocks(markdown);
  let processedMarkdown = displayExtraction.text;

  // Extract inline math blocks to protect full \(...\) expressions
  const inlineExtraction = extractInlineMathBlocks(processedMarkdown);
  processedMarkdown = inlineExtraction.text;

  // Fix Korean bold spans before parsing
  // This ensures **text**로 renders correctly as **text로**
  processedMarkdown = fixKoreanBoldSpans(processedMarkdown);

  let html = '';
  if (typeof marked !== 'undefined') {
    try {
      html = marked.parse(processedMarkdown);
    } catch (e) {
      console.error('Markdown parsing error:', e);
      html = escapeHtml(processedMarkdown).replace(/\n/g, '<br>');
    }
  } else {
    // Fallback: just escape HTML and convert newlines
    html = escapeHtml(processedMarkdown).replace(/\n/g, '<br>');
  }

  // Restore LaTeX blocks after markdown processing
  html = restoreInlineMathBlocks(html, inlineExtraction.blocks);
  html = restoreDisplayMathBlocks(html, displayExtraction.blocks);

  return html;
}

/**
 * Apply syntax highlighting to code blocks in an element using highlight.js
 * @param {HTMLElement} element - The DOM element to process
 */
function applySyntaxHighlighting(element) {
  if (typeof hljs !== 'undefined') {
    // Find all code blocks and highlight them
    const codeBlocks = element.querySelectorAll('pre code');
    codeBlocks.forEach((block) => {
      hljs.highlightElement(block);
    });
  }
}

/**
 * Apply all post-render enhancements to an element:
 * - KaTeX math rendering
 * - Syntax highlighting
 * @param {HTMLElement} element - The DOM element to process
 */
function applyRenderEnhancements(element) {
  // Apply KaTeX math rendering
  if (typeof window.renderMathInElement === 'function' && typeof katex !== 'undefined') {
    window.renderMathInElement(element, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false }
      ],
      throwOnError: false,
      errorColor: '#cc0000'
    });
  }

  // Apply syntax highlighting to code blocks
  applySyntaxHighlighting(element);
}


/**
 * Toggle between description view and edit modes
 */
function toggleDescriptionMode() {
  const textarea = document.getElementById('modal-description');
  const viewDiv = document.getElementById('modal-description-view');
  const toggleBtn = document.getElementById('description-toggle-btn');
  const toggleIcon = document.getElementById('description-toggle-icon');
  const toggleLabel = document.getElementById('description-toggle-label');

  smoothStickyToggle.reset();

  if (descriptionMode === 'edit') {
    // Switch to view mode
    descriptionMode = 'view';
    const content = textarea.value.trim();

    if (content) {
      viewDiv.innerHTML = renderMarkdown(content);
      applyRenderEnhancements(viewDiv);
      viewDiv.classList.remove('empty');
    } else {
      viewDiv.innerHTML = 'No description';
      viewDiv.classList.add('empty');
    }

    textarea.style.display = 'none';
    viewDiv.style.display = 'block';
    toggleBtn.classList.add('active');
    toggleIcon.setAttribute('data-lucide', 'pencil');
    toggleLabel.textContent = 'Edit';
  } else {
    // Switch to edit mode
    descriptionMode = 'edit';
    textarea.style.display = 'block';
    viewDiv.style.display = 'none';
    toggleBtn.classList.remove('active');
    toggleIcon.setAttribute('data-lucide', 'eye');
    toggleLabel.textContent = 'View';
    textarea.focus();
  }

  refreshIcons(toggleBtn);
}

/**
 * Set the description mode without toggling
 * @param {string} mode - 'view' or 'edit'
 */
function setDescriptionMode(mode) {
  const textarea = document.getElementById('modal-description');
  const viewDiv = document.getElementById('modal-description-view');
  const toggleBtn = document.getElementById('description-toggle-btn');
  const toggleIcon = document.getElementById('description-toggle-icon');
  const toggleLabel = document.getElementById('description-toggle-label');

  descriptionMode = mode;

  if (mode === 'view') {
    const content = textarea.value.trim();

    if (content) {
      viewDiv.innerHTML = renderMarkdown(content);
      applyRenderEnhancements(viewDiv);
      viewDiv.classList.remove('empty');
    } else {
      viewDiv.innerHTML = 'No description';
      viewDiv.classList.add('empty');
    }

    textarea.style.display = 'none';
    viewDiv.style.display = 'block';
    toggleBtn.classList.add('active');
    toggleIcon.setAttribute('data-lucide', 'pencil');
    toggleLabel.textContent = 'Edit';
  } else {
    textarea.style.display = 'block';
    viewDiv.style.display = 'none';
    toggleBtn.classList.remove('active');
    toggleIcon.setAttribute('data-lucide', 'eye');
    toggleLabel.textContent = 'View';
  }

  refreshIcons(toggleBtn);
}

/**
 * Store the current modal field values as original values for dirty checking.
 */
function storeOriginalModalValues() {
  const titleInput = document.getElementById('modal-title');
  const statusSelect = document.getElementById('modal-status-select');
  const prioritySelect = document.getElementById('modal-priority');
  const descriptionInput = document.getElementById('modal-description');

  originalModalValues = {
    title: titleInput?.value || '',
    status: statusSelect?.value || '',
    priority: prioritySelect?.value || '',
    description: descriptionInput?.value || '',
    dueDate: datePicker.getISODate() || ''
  };
}

/**
 * Check if the modal form has unsaved changes.
 * @returns {boolean} True if there are unsaved changes
 */
function isModalDirty() {
  const titleInput = document.getElementById('modal-title');
  const statusSelect = document.getElementById('modal-status-select');
  const prioritySelect = document.getElementById('modal-priority');
  const descriptionInput = document.getElementById('modal-description');

  const currentValues = {
    title: titleInput?.value || '',
    status: statusSelect?.value || '',
    priority: prioritySelect?.value || '',
    description: descriptionInput?.value || '',
    dueDate: datePicker.getISODate() || ''
  };

  // Check if any value has changed
  return (
    currentValues.title !== originalModalValues.title ||
    currentValues.status !== originalModalValues.status ||
    currentValues.priority !== originalModalValues.priority ||
    currentValues.description !== originalModalValues.description ||
    currentValues.dueDate !== originalModalValues.dueDate
  );
}

/**
 * Attempt to close the modal with unsaved changes confirmation.
 * @param {boolean} skipConfirmation - If true, close without confirmation
 * @returns {boolean} True if modal was closed, false if user cancelled
 */
async function tryCloseTaskModal(skipConfirmation = false) {
  if (!skipConfirmation && isModalDirty()) {
    const confirmed = await showConfirm({
      title: 'Unsaved Changes',
      message: 'You have unsaved changes. Are you sure you want to close without saving?',
      confirmText: 'Discard',
      cancelText: 'Keep Editing',
      type: 'warning'
    });
    if (!confirmed) {
      return false;
    }
  }
  closeTaskModal();
  return true;
}

function openCreateTaskModal(parentId = null) {
  modalMode = 'create';
  createTaskParentId = parentId;
  currentModalTaskId = null;

  const modal = document.getElementById('task-modal');
  const titleInput = document.getElementById('modal-title');
  const statusSelect = document.getElementById('modal-status-select');
  const prioritySelect = document.getElementById('modal-priority');
  const descriptionInput = document.getElementById('modal-description');
  const statusBtn = document.getElementById('modal-status-btn');

  // Clear all fields
  titleInput.value = '';
  statusSelect.value = 'pending';
  prioritySelect.value = '4';  // Default to Low priority
  descriptionInput.value = '';

  // Set current date as default due date using date picker
  const now = new Date();
  datePicker.setDate(now.toISOString());

  // Reset status button to unchecked
  statusBtn.classList.remove('checked');
  statusBtn.innerHTML = '<i data-lucide="circle"></i>';

  // Hide sections not relevant for create mode
  document.querySelector('.modal-metadata').style.display = 'none';
  document.getElementById('modal-delete').style.display = 'none';
  document.querySelector('#modal-subtasks').parentElement.style.display = 'none';
  document.querySelector('#modal-attachments').parentElement.style.display = 'none';

  // Change button text and header context
  const saveBtn = document.getElementById('modal-save');
  saveBtn.innerHTML = '<i data-lucide="plus"></i><span>Create Task</span>';

  // Update modal title placeholder
  titleInput.placeholder = parentId ? 'New subtask title...' : 'New task title...';

  // Reset floating button position for the new modal
  smoothStickyToggle.reset();

  // Set description to edit mode for creating new tasks
  setDescriptionMode('edit');

  // Show modal
  modal.style.display = 'flex';
  refreshIcons(modal);

  // Store original values for dirty checking (after setting defaults)
  setTimeout(() => storeOriginalModalValues(), 0);

  // Focus title after animation
  setTimeout(() => titleInput.focus(), ANIMATION.fast);
}

function openTaskModal(taskId) {
  modalMode = 'edit';
  createTaskParentId = null;

  const task = state.tasks.get(taskId);
  if (!task) return;

  currentModalTaskId = taskId;

  const modal = document.getElementById('task-modal');
  const titleInput = document.getElementById('modal-title');
  const statusSelect = document.getElementById('modal-status-select');
  const prioritySelect = document.getElementById('modal-priority');
  const descriptionInput = document.getElementById('modal-description');
  const statusBtn = document.getElementById('modal-status-btn');
  const createdEl = document.getElementById('modal-created');
  const updatedEl = document.getElementById('modal-updated');

  // Populate fields
  titleInput.value = task.title;
  statusSelect.value = task.status;
  prioritySelect.value = task.priority || '';
  descriptionInput.value = task.description || '';
  titleInput.placeholder = 'Task title...';

  // Set due date using date picker
  datePicker.setDate(task.next_due_utc || null);

  // Status button
  const isCompleted = task.status === 'completed';
  statusBtn.classList.toggle('checked', isCompleted);
  statusBtn.innerHTML = `<i data-lucide="${isCompleted ? 'check-circle-2' : 'circle'}"></i>`;

  // Metadata
  createdEl.textContent = `Created: ${formatDate(task.created_at)}`;
  updatedEl.textContent = `Updated: ${formatDate(task.updated_at)}`;

  // Show all sections for edit mode
  document.querySelector('.modal-metadata').style.display = 'flex';
  document.getElementById('modal-delete').style.display = 'inline-flex';
  document.querySelector('#modal-subtasks').parentElement.style.display = 'block';
  document.querySelector('#modal-attachments').parentElement.style.display = 'block';

  // Change button text back to edit mode
  const saveBtn = document.getElementById('modal-save');
  saveBtn.innerHTML = '<i data-lucide="check"></i><span>Save Changes</span>';

  // Load subtasks and attachments
  renderModalSubtasks(taskId);
  loadModalAttachments(taskId);

  // Reset floating button position for the new modal
  smoothStickyToggle.reset();

  // Set description mode: view if content exists, edit if empty
  if (task.description && task.description.trim()) {
    setDescriptionMode('view');
  } else {
    setDescriptionMode('edit');
  }

  // Show modal with animation
  modal.style.display = 'flex';
  refreshIcons(modal);

  // Store original values for dirty checking (after setting values)
  setTimeout(() => storeOriginalModalValues(), 0);

  // Focus title after animation
  setTimeout(() => {
    titleInput.focus();
    titleInput.select();
  }, ANIMATION.fast);
}

function closeTaskModal() {
  const modal = document.getElementById('task-modal');
  const container = modal.querySelector('.modal-container');

  // Add closing animation
  modal.classList.add('closing');
  container.classList.add('closing');

  // Wait for animation to complete before hiding
  setTimeout(() => {
    modal.style.display = 'none';
    modal.classList.remove('closing');
    container.classList.remove('closing');
    currentModalTaskId = null;
    modalMode = 'edit';
    createTaskParentId = null;
  }, ANIMATION.normal);
}

async function saveTaskModal() {
  if (modalMode === 'create') {
    await createTaskFromModal();
  } else {
    await updateTaskFromModal();
  }
}

async function createTaskFromModal() {
  const titleInput = document.getElementById('modal-title');
  const statusSelect = document.getElementById('modal-status-select');
  const prioritySelect = document.getElementById('modal-priority');
  const descriptionInput = document.getElementById('modal-description');

  const title = titleInput.value.trim();
  if (!title) {
    showToast('Title is required', 'error');
    titleInput.focus();
    return;
  }

  // Get date from date picker
  const isoDate = datePicker.getISODate();

  const taskData = {
    title,
    status: statusSelect.value,
    priority: prioritySelect.value ? parseInt(prioritySelect.value) : null,
    description: descriptionInput.value.trim() || null,
    next_due_utc: isoDate ? new Date(isoDate).toISOString() : null,
    parent_id: createTaskParentId
  };

  try {
    state.isLocalAction = true;
    await createTask(taskData);

    // Auto-expand parent task when subtask is added
    if (createTaskParentId) {
      state.expandedTasks.add(createTaskParentId);
      saveExpandedTasksToStorage();
    }

    await loadTasks();
    // Note: loadTasks() already calls renderTaskTree() and updateStats()
    closeTaskModal();
    showToast('Task created', 'success');
  } catch (error) {
    showToast('Failed to create task', 'error');
  } finally {
    setTimeout(() => { state.isLocalAction = false; }, 500);
  }
}

async function updateTaskFromModal() {
  if (!currentModalTaskId) return;

  const titleInput = document.getElementById('modal-title');
  const statusSelect = document.getElementById('modal-status-select');
  const prioritySelect = document.getElementById('modal-priority');
  const descriptionInput = document.getElementById('modal-description');

  const title = titleInput.value.trim();
  if (!title) {
    showToast('Title is required', 'error');
    titleInput.focus();
    return;
  }

  // Get date from date picker
  const isoDate = datePicker.getISODate();

  const taskData = {
    title,
    status: statusSelect.value,
    priority: prioritySelect.value ? parseInt(prioritySelect.value) : null,
    description: descriptionInput.value.trim() || null,
    next_due_utc: isoDate ? new Date(isoDate).toISOString() : null
  };

  try {
    state.isLocalAction = true;
    await updateTask(currentModalTaskId, taskData);

    // Update local state
    const task = state.tasks.get(currentModalTaskId);
    if (task) {
      Object.assign(task, taskData);
      renderTaskTree();
      updateStats();
    }

    closeTaskModal();
    showToast('Task updated', 'success');

  } catch (error) {
    showToast('Failed to update task', 'error');
  } finally {
    setTimeout(() => { state.isLocalAction = false; }, 500);
  }
}

async function deleteTaskFromModal() {
  if (!currentModalTaskId) return;

  const task = state.tasks.get(currentModalTaskId);
  if (!task) return;

  const confirmed = await showConfirm({
    title: 'Delete Task',
    message: `This will delete "${task.title}".`,
    confirmText: 'Delete',
    type: 'danger'
  });

  if (confirmed) {
    try {
      state.isLocalAction = true;
      await deleteTask(currentModalTaskId);
      closeTaskModal();
      await loadTasks();
      showToast('Task deleted', 'success');
    } catch (error) {
      showToast('Failed to delete task', 'error');
    } finally {
      setTimeout(() => { state.isLocalAction = false; }, 500);
    }
  }
}

function renderModalSubtasks(taskId) {
  const container = document.getElementById('modal-subtasks');
  const task = state.tasks.get(taskId);

  if (!task || !task.childIds || task.childIds.length === 0) {
    container.innerHTML = '<div class="attachments-empty">No subtasks yet</div>';
    return;
  }

  container.innerHTML = task.childIds.map(childId => {
    const child = state.tasks.get(childId);
    if (!child || child.status === 'deleted') return '';

    const isCompleted = child.status === 'completed';
    return `
      <div class="subtask-item ${isCompleted ? 'completed' : ''}" data-task-id="${childId}">
        <button class="checkbox ${isCompleted ? 'checked' : ''}" data-action="toggle-subtask">
          <i data-lucide="${isCompleted ? 'check-circle-2' : 'circle'}"></i>
        </button>
        <span class="subtask-title" data-action="open-subtask">${escapeHtml(child.title)}</span>
      </div>
    `;
  }).join('');

  // Event listeners
  container.querySelectorAll('.subtask-item').forEach(item => {
    const childId = parseInt(item.dataset.taskId);

    item.querySelector('[data-action="toggle-subtask"]')?.addEventListener('click', async () => {
      await toggleComplete(childId);
      renderModalSubtasks(taskId);
    });

    item.querySelector('[data-action="open-subtask"]')?.addEventListener('click', () => {
      openTaskModal(childId);
    });
  });

  refreshIcons(container);
}

async function loadModalAttachments(taskId) {
  const container = document.getElementById('modal-attachments');

  try {
    const attachments = await fetchTaskAttachments(taskId);

    if (!attachments || attachments.length === 0) {
      container.innerHTML = '<div class="attachments-empty">No attachments</div>';
      return;
    }

    container.innerHTML = attachments.map(att => `
      <div class="attachment-item" data-attachment-id="${att.id}">
        <div class="attachment-icon">
          <i data-lucide="file"></i>
        </div>
        <div class="attachment-info">
          <div class="attachment-name" title="${escapeHtml(att.filename)}">${escapeHtml(att.filename)}</div>
          <div class="attachment-size">${formatFileSize(att.size_bytes)}</div>
        </div>
        <div class="attachment-actions">
          <button class="download-btn" title="Download">
            <i data-lucide="download"></i>
          </button>
          <button class="delete-btn" title="Delete">
            <i data-lucide="trash-2"></i>
          </button>
        </div>
      </div>
    `).join('');

    // Event listeners
    container.querySelectorAll('.attachment-item').forEach(item => {
      const attId = parseInt(item.dataset.attachmentId);

      item.querySelector('.download-btn')?.addEventListener('click', () => {
        window.open(getAttachmentDownloadUrl(attId), '_blank');
      });

      item.querySelector('.delete-btn')?.addEventListener('click', async () => {
        const confirmed = await showConfirm({
          title: 'Delete Attachment',
          message: 'Are you sure you want to delete this attachment?',
          confirmText: 'Delete',
          type: 'danger'
        });

        if (confirmed) {
          try {
            await deleteAttachment(attId);
            loadModalAttachments(taskId);
            showToast('Attachment deleted', 'success');
          } catch (error) {
            showToast('Failed to delete attachment', 'error');
          }
        }
      });
    });

    refreshIcons(container);

  } catch (error) {
    container.innerHTML = '<div class="attachments-empty">Failed to load attachments</div>';
  }
}

async function handleFileUpload(files) {
  if (!currentModalTaskId || !files || files.length === 0) return;

  for (const file of files) {
    try {
      await uploadAttachment(currentModalTaskId, file);
      showToast(`Uploaded ${file.name}`, 'success');
    } catch (error) {
      showToast(`Failed to upload ${file.name}`, 'error');
    }
  }

  loadModalAttachments(currentModalTaskId);
}

// ============================================
// Stats & Header
// ============================================
function updateStats() {
  let total = 0;
  let completed = 0;

  state.tasks.forEach(task => {
    if (task.status !== 'deleted') {
      total++;
      if (task.status === 'completed') completed++;
    }
  });

  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  // Update stats with smooth counter animation
  const percentageEl = document.getElementById('stat-percentage');
  const completedEl = document.getElementById('stat-completed');
  const totalEl = document.getElementById('stat-total');

  if (percentageEl) percentageEl.textContent = `${percentage}%`;
  if (completedEl) completedEl.textContent = `${completed} done`;
  if (totalEl) totalEl.textContent = `of ${total} tasks`;

  // Animate progress ring
  const progressCircle = document.getElementById('progress-circle');
  if (progressCircle) {
    progressCircle.style.strokeDasharray = `${percentage}, 100`;
  }
}

async function updateUndoRedoStatus() {
  try {
    const status = await fetchUndoStatus();
    state.undoEnabled = status.can_undo;
    state.redoEnabled = status.can_redo;

    const undoBtn = document.getElementById('undo-btn');
    const redoBtn = document.getElementById('redo-btn');

    if (undoBtn) undoBtn.disabled = !status.can_undo;
    if (redoBtn) redoBtn.disabled = !status.can_redo;
  } catch (error) {
    // Ignore errors
  }
}

// ============================================
// Search & Filter
// ============================================
function handleSearch(query) {
  state.searchQuery = query;
  renderTaskTree();

  const clearBtn = document.getElementById('search-clear');
  if (clearBtn) {
    clearBtn.style.display = query ? 'flex' : 'none';
  }
}

function setFilter(filter) {
  state.currentFilter = filter;

  // Save to localStorage for persistence
  saveFilterToStorage();

  // Update UI
  document.querySelectorAll('.filter-option').forEach(opt => {
    opt.classList.toggle('active', opt.dataset.filter === filter);
  });

  const filterLabel = document.getElementById('filter-label');
  if (filterLabel) {
    filterLabel.textContent = filter === 'all' ? 'All' : STATUS_LABELS[filter] || filter.replace('_', ' ');
  }

  // Close dropdown (portal menu)
  closeFilterMenu();

  renderTaskTree();
}

// ============================================
// Filter Dropdown (Portal + Positioning)
// ============================================
let filterMenuEl = null;
let filterBtnEl = null;
let filterDropdownEl = null;

function positionFilterMenu() {
  if (!filterMenuEl || !filterBtnEl) return;
  const rect = filterBtnEl.getBoundingClientRect();
  filterMenuEl.style.left = `${Math.round(rect.left)}px`;
  filterMenuEl.style.top = `${Math.round(rect.bottom + 8)}px`;
  filterMenuEl.style.minWidth = `${Math.max(180, Math.round(rect.width))}px`;
}

function openFilterMenu() {
  if (!filterMenuEl || !filterDropdownEl) return;
  filterDropdownEl.classList.add('open');

  // Move menu to body to avoid being clipped / losing z-order to the task list.
  if (filterMenuEl.parentElement !== document.body) {
    document.body.appendChild(filterMenuEl);
  }

  positionFilterMenu();
  filterMenuEl.classList.add('open');
}

function closeFilterMenu() {
  if (!filterMenuEl || !filterDropdownEl) return;
  filterDropdownEl.classList.remove('open');
  filterMenuEl.classList.remove('open');
}

// ============================================
// Expand/Collapse All
// ============================================
function expandAll() {
  state.tasks.forEach((task, id) => {
    if (task.childIds && task.childIds.length > 0) {
      state.expandedTasks.add(id);
    }
  });
  saveExpandedTasksToStorage();
  renderTaskTree();
  showToast('All tasks expanded', 'info');
}

function collapseAll() {
  state.expandedTasks.clear();
  saveExpandedTasksToStorage();
  renderTaskTree();
  showToast('All tasks collapsed', 'info');
}

// ============================================
// Keyboard Navigation
// ============================================
function handleGlobalKeydown(e) {
  // Ignore if typing in an input
  if (e.target.matches('input, textarea, select')) {
    if (e.key === 'Escape') {
      e.target.blur();
    }
    return;
  }

  // Ignore keyboard navigation if confirmation modal is open (except Escape which is handled separately)
  if (confirmResolve !== null && e.key !== 'Escape') {
    return;
  }

  switch (e.key) {
    case '/':
      e.preventDefault();
      document.getElementById('search-input')?.focus();
      break;

    case 'n':
    case 'N':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        openCreateTaskModal();
      }
      break;

    case 'e':
    case 'E':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        expandAll();
      }
      break;

    case 'c':
    case 'C':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        collapseAll();
      }
      break;

    case '?':
      e.preventDefault();
      toggleShortcutsModal();
      break;

    case 'Escape':
      // Check if confirmation modal is open - let its own handler deal with it
      const confirmModal = document.getElementById('confirm-modal');
      if (confirmModal?.style.display !== 'none') {
        // Confirm modal is open, don't process Escape here
        // The confirm modal's own listener will handle it
        break;
      }

      // Close modals first, then clear selection if no modals were open
      const taskModal = document.getElementById('task-modal');
      const shortcutsModal = document.getElementById('shortcuts-modal');

      const taskModalOpen = taskModal.style.display !== 'none';
      const shortcutsModalOpen = shortcutsModal.style.display !== 'none';

      if (taskModalOpen) {
        // Task modal: check for unsaved changes
        tryCloseTaskModal();
      } else if (shortcutsModalOpen) {
        toggleShortcutsModal();
      } else {
        // No modals open, clear task selection
        clearSelection();
      }
      break;

    case 'ArrowUp':
      e.preventDefault();
      navigateTasks(-1);
      break;

    case 'ArrowDown':
      e.preventDefault();
      navigateTasks(1);
      break;

    case 'ArrowLeft':
      if (state.selectedTaskId) {
        const task = state.tasks.get(state.selectedTaskId);
        if (task && state.expandedTasks.has(state.selectedTaskId)) {
          toggleExpand(state.selectedTaskId);
        }
      }
      break;

    case 'ArrowRight':
      if (state.selectedTaskId) {
        const task = state.tasks.get(state.selectedTaskId);
        if (task && task.childIds?.length > 0 && !state.expandedTasks.has(state.selectedTaskId)) {
          toggleExpand(state.selectedTaskId);
        }
      }
      break;

    case 'Enter':
      if (state.selectedTaskId) {
        openTaskModal(state.selectedTaskId);
      }
      break;

    case ' ':
      e.preventDefault();
      if (state.selectedTaskId) {
        toggleComplete(state.selectedTaskId);
      }
      break;

    case '+':
    case '=':
      if (state.selectedTaskId) {
        e.preventDefault();
        openCreateTaskModal(state.selectedTaskId);
      }
      break;

    case 'Delete':
    case 'Backspace':
      if (state.selectedTaskId && !e.target.matches('input, textarea')) {
        e.preventDefault();
        confirmDeleteTask(state.selectedTaskId);
      }
      break;

    case 'z':
    case 'Z':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        // Shift+Ctrl/Cmd+Z = redo (standard on macOS), plain = undo
        if (e.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
      }
      break;

    case 'y':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        handleRedo();
      }
      break;
  }
}

function navigateTasks(direction) {
  const items = Array.from(document.querySelectorAll('.todo-item'));
  if (items.length === 0) return;

  const currentIndex = items.findIndex(
    item => parseInt(item.dataset.taskId) === state.selectedTaskId
  );

  let newIndex;
  if (currentIndex === -1) {
    newIndex = direction > 0 ? 0 : items.length - 1;
  } else {
    newIndex = currentIndex + direction;
    if (newIndex < 0) newIndex = items.length - 1;
    if (newIndex >= items.length) newIndex = 0;
  }

  const newTaskId = parseInt(items[newIndex].dataset.taskId);
  selectTask(newTaskId);
  scrollToElement(items[newIndex], { block: 'nearest' });
}

function closeAllModals() {
  const taskModal = document.getElementById('task-modal');
  const shortcutsModal = document.getElementById('shortcuts-modal');

  // Use animated close for task modal if visible
  if (taskModal.style.display !== 'none') {
    closeTaskModal();
  }

  // Close shortcuts modal (no animation needed)
  shortcutsModal.style.display = 'none';
}

function toggleShortcutsModal() {
  const modal = document.getElementById('shortcuts-modal');
  modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
}

// ============================================
// Custom Date Picker
// ============================================
const datePicker = {
  currentDate: new Date(),
  selectedDate: null,
  isOpen: false,
  selectionMode: 'days', // 'days' or 'monthYear'
  yearRangeStart: new Date().getFullYear() - 6,

  monthNames: ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'],
  monthNamesShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  dayNames: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],

  init() {
    this.popup = document.getElementById('calendar-popup');
    this.backdrop = document.getElementById('calendar-backdrop');
    this.grid = document.getElementById('calendar-grid');
    this.monthYear = document.getElementById('calendar-month-year');
    this.input = document.getElementById('modal-due-date');
    this.trigger = document.getElementById('calendar-trigger');
    this.clearBtn = document.getElementById('clear-date-btn');
    this.prevBtn = document.getElementById('prev-month');
    this.nextBtn = document.getElementById('next-month');
    this.todayBtn = document.getElementById('calendar-today-btn');

    // Month/Year selection elements
    this.selectionPanel = document.getElementById('calendar-selection-panel');
    this.yearGrid = document.getElementById('calendar-year-grid');
    this.monthGrid = document.getElementById('calendar-month-grid');
    this.yearRange = document.getElementById('calendar-year-range');
    this.prevYearRange = document.getElementById('prev-year-range');
    this.nextYearRange = document.getElementById('next-year-range');

    if (!this.popup || !this.input) return;

    this.setupEventListeners();
  },

  setupEventListeners() {
    // Open calendar only when clicking the calendar icon (SVG trigger)
    this.trigger?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.show();
    });

    // Make input editable for manual date entry
    if (this.input) {
      this.input.removeAttribute('readonly');
      this.input.addEventListener('change', (e) => {
        this.parseAndSetDate(e.target.value);
      });
    }

    // Close on backdrop click
    this.backdrop?.addEventListener('click', () => this.hide());

    // Navigation
    this.prevBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.currentDate.setMonth(this.currentDate.getMonth() - 1);
      this.render();
    });

    this.nextBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.currentDate.setMonth(this.currentDate.getMonth() + 1);
      this.render();
    });

    // Today button
    this.todayBtn?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const today = new Date();
      this.selectDate(today);
    });

    // Clear button
    this.clearBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.clearDate();
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.hide();
      }
    });

    // Month/Year selection toggle
    this.monthYear?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleSelectionMode();
    });

    // Year range navigation
    this.prevYearRange?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.yearRangeStart -= 12;
      this.renderYearGrid();
    });

    this.nextYearRange?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.yearRangeStart += 12;
      this.renderYearGrid();
    });
  },

  toggleSelectionMode() {
    if (this.selectionMode === 'days') {
      this.selectionMode = 'monthYear';
      this.yearRangeStart = this.currentDate.getFullYear() - 6;
      this.showSelectionPanel();
    } else {
      this.selectionMode = 'days';
      this.hideSelectionPanel();
    }
  },

  showSelectionPanel() {
    if (this.selectionPanel) {
      this.selectionPanel.style.display = 'block';
      this.renderYearGrid();
      this.renderMonthGrid();
    }
    if (this.grid) {
      this.grid.style.display = 'none';
    }
  },

  hideSelectionPanel() {
    if (this.selectionPanel) {
      this.selectionPanel.style.display = 'none';
    }
    if (this.grid) {
      this.grid.style.display = 'grid';
    }
  },

  renderYearGrid() {
    if (!this.yearGrid || !this.yearRange) return;

    const currentYear = new Date().getFullYear();
    const selectedYear = this.currentDate.getFullYear();
    const endYear = this.yearRangeStart + 11;

    this.yearRange.textContent = `${this.yearRangeStart} - ${endYear}`;
    this.yearGrid.innerHTML = '';

    for (let year = this.yearRangeStart; year <= endYear; year++) {
      const yearEl = document.createElement('div');
      yearEl.className = 'calendar-year-item';
      yearEl.textContent = year;

      if (year === selectedYear) {
        yearEl.classList.add('selected');
      }
      if (year === currentYear) {
        yearEl.classList.add('current');
      }

      const clickYear = year;
      yearEl.addEventListener('click', () => this.selectYear(clickYear));
      this.yearGrid.appendChild(yearEl);
    }
  },

  renderMonthGrid() {
    if (!this.monthGrid) return;

    const currentMonth = new Date().getMonth();
    const currentYear = new Date().getFullYear();
    const selectedMonth = this.currentDate.getMonth();
    const selectedYear = this.currentDate.getFullYear();

    this.monthGrid.innerHTML = '';

    for (let month = 0; month < 12; month++) {
      const monthEl = document.createElement('div');
      monthEl.className = 'calendar-month-item';
      monthEl.textContent = this.monthNamesShort[month];

      if (month === selectedMonth) {
        monthEl.classList.add('selected');
      }
      if (month === currentMonth && selectedYear === currentYear) {
        monthEl.classList.add('current');
      }

      const clickMonth = month;
      monthEl.addEventListener('click', () => this.selectMonth(clickMonth));
      this.monthGrid.appendChild(monthEl);
    }
  },

  selectYear(year) {
    this.currentDate.setFullYear(year);
    this.renderYearGrid();
    this.renderMonthGrid();
    this.updateMonthYearDisplay();
  },

  selectMonth(month) {
    this.currentDate.setMonth(month);
    this.selectionMode = 'days';
    this.hideSelectionPanel();
    this.render();
  },

  updateMonthYearDisplay() {
    if (this.monthYear) {
      const year = this.currentDate.getFullYear();
      const month = this.currentDate.getMonth();
      this.monthYear.textContent = `${this.monthNames[month]} ${year}`;
    }
  },

  show() {
    if (this.selectedDate) {
      this.currentDate = new Date(this.selectedDate);
    } else {
      this.currentDate = new Date();
    }
    // Reset to days view when opening
    this.selectionMode = 'days';
    this.hideSelectionPanel();
    this.render();
    this.popup?.classList.add('show');
    this.backdrop?.classList.add('show');
    this.isOpen = true;
  },

  hide() {
    this.popup?.classList.remove('show');
    this.backdrop?.classList.remove('show');
    this.isOpen = false;
    // Reset to days view when closing
    this.selectionMode = 'days';
    this.hideSelectionPanel();
  },

  render() {
    if (!this.grid || !this.monthYear) return;

    const year = this.currentDate.getFullYear();
    const month = this.currentDate.getMonth();

    // Update header
    this.monthYear.textContent = `${this.monthNames[month]} ${year}`;

    // Calculate dates
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay());

    this.grid.innerHTML = '';

    // Day headers
    this.dayNames.forEach(day => {
      const header = document.createElement('div');
      header.className = 'calendar-day-header';
      header.textContent = day;
      this.grid.appendChild(header);
    });

    // Render 6 weeks (42 days)
    for (let i = 0; i < 42; i++) {
      const date = new Date(startDate);
      date.setDate(startDate.getDate() + i);

      const dayEl = document.createElement('div');
      dayEl.className = 'calendar-day';
      dayEl.textContent = date.getDate();

      // Add classes
      if (date.getMonth() !== month) {
        dayEl.classList.add('other-month');
      }
      if (this.isToday(date)) {
        dayEl.classList.add('today');
      }
      if (this.selectedDate && this.isSameDate(date, this.selectedDate)) {
        dayEl.classList.add('selected');
      }

      // Click handler
      const clickDate = new Date(date);
      dayEl.addEventListener('click', () => this.selectDate(clickDate));

      this.grid.appendChild(dayEl);
    }
  },

  selectDate(date) {
    this.selectedDate = date;
    if (this.input) {
      this.input.value = this.formatDisplayDate(date);
      this.input.dataset.isoDate = this.formatISODate(date);
    }
    this.hide();
  },

  clearDate() {
    this.selectedDate = null;
    if (this.input) {
      this.input.value = '';
      delete this.input.dataset.isoDate;
    }
  },

  setDate(dateStr) {
    if (dateStr) {
      this.selectedDate = new Date(dateStr);
      if (this.input) {
        this.input.value = this.formatDisplayDate(this.selectedDate);
        this.input.dataset.isoDate = this.formatISODate(this.selectedDate);
      }
    } else {
      this.clearDate();
    }
  },

  getISODate() {
    return this.input?.dataset.isoDate || null;
  },

  formatDisplayDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  },

  parseAndSetDate(dateStr) {
    if (!dateStr || !dateStr.trim()) {
      this.clearDate();
      return;
    }
    // Try to parse YYYY-MM-DD format
    const match = dateStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (match) {
      const year = parseInt(match[1], 10);
      const month = parseInt(match[2], 10) - 1;
      const day = parseInt(match[3], 10);
      const date = new Date(year, month, day);
      if (!isNaN(date.getTime())) {
        this.selectedDate = date;
        if (this.input) {
          this.input.value = this.formatDisplayDate(date);
          this.input.dataset.isoDate = this.formatISODate(date);
        }
        return;
      }
    }
    // If parsing fails, try native Date parsing as fallback
    const parsed = new Date(dateStr);
    if (!isNaN(parsed.getTime())) {
      this.selectedDate = parsed;
      if (this.input) {
        this.input.value = this.formatDisplayDate(parsed);
        this.input.dataset.isoDate = this.formatISODate(parsed);
      }
    }
  },

  formatISODate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}T00:00:00`;
  },

  isToday(date) {
    const today = new Date();
    return date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear();
  },

  isSameDate(date1, date2) {
    if (!date1 || !date2) return false;
    return date1.getDate() === date2.getDate() &&
      date1.getMonth() === date2.getMonth() &&
      date1.getFullYear() === date2.getFullYear();
  }
};

// ============================================
// Undo/Redo
// ============================================
async function handleUndo() {
  if (!state.undoEnabled) return;

  try {
    state.isLocalAction = true;
    await performUndo();
    await loadTasks();
    showToast('Undone', 'success');
  } catch (error) {
    showToast('Nothing to undo', 'info');
  } finally {
    setTimeout(() => { state.isLocalAction = false; }, 500);
  }
}

async function handleRedo() {
  if (!state.redoEnabled) return;

  try {
    state.isLocalAction = true;
    await performRedo();
    await loadTasks();
    showToast('Redone', 'success');
  } catch (error) {
    showToast('Nothing to redo', 'info');
  } finally {
    setTimeout(() => { state.isLocalAction = false; }, 500);
  }
}

// ============================================
// Custom Confirmation Modal
// ============================================
let confirmResolve = null;
let confirmModalOpenedAt = 0; // Timestamp when confirm modal was opened

/**
 * Show a custom confirmation modal.
 * @param {Object} options - Configuration options
 * @param {string} options.title - Modal title
 * @param {string} options.message - Modal message
 * @param {string} options.confirmText - Text for confirm button (default: 'Confirm')
 * @param {string} options.cancelText - Text for cancel button (default: 'Cancel')
 * @param {string} options.type - Icon type: 'danger', 'warning', 'info' (default: 'danger')
 * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
 */
function showConfirm({
  title = 'Confirm Action',
  message = 'Are you sure you want to proceed?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  type = 'danger'
} = {}) {
  return new Promise((resolve) => {
    confirmResolve = resolve;

    const modal = document.getElementById('confirm-modal');
    const titleEl = document.getElementById('confirm-title');
    const messageEl = document.getElementById('confirm-message');
    const iconEl = document.getElementById('confirm-icon');
    const okBtn = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');

    // Set content
    titleEl.textContent = title;
    messageEl.textContent = message;
    okBtn.textContent = confirmText;
    cancelBtn.textContent = cancelText;

    // Set icon based on type
    const icons = {
      danger: 'alert-triangle',
      warning: 'alert-circle',
      info: 'help-circle'
    };
    iconEl.className = `confirm-icon ${type}`;
    iconEl.innerHTML = `<i data-lucide="${icons[type] || icons.danger}"></i>`;

    // Style confirm button based on type
    okBtn.className = type === 'danger' ? 'btn btn-danger' : 'btn btn-primary';

    // Show modal and record when it was opened
    modal.style.display = 'flex';
    modal.classList.remove('closing');
    confirmModalOpenedAt = Date.now();
    refreshIcons(modal);

    // Focus the cancel button (safer default)
    setTimeout(() => cancelBtn.focus(), 50);
  });
}

function closeConfirmModal(result) {
  const modal = document.getElementById('confirm-modal');
  modal.classList.add('closing');

  setTimeout(() => {
    modal.style.display = 'none';
    modal.classList.remove('closing');
    if (confirmResolve) {
      confirmResolve(result);
      confirmResolve = null;
    }
  }, 200);
}

function setupConfirmModalListeners() {
  const modal = document.getElementById('confirm-modal');
  const okBtn = document.getElementById('confirm-ok');
  const cancelBtn = document.getElementById('confirm-cancel');

  okBtn?.addEventListener('click', () => closeConfirmModal(true));
  cancelBtn?.addEventListener('click', () => closeConfirmModal(false));

  // Click outside to cancel
  modal?.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
      closeConfirmModal(false);
    }
  });

  // Escape to cancel (with debounce to prevent same keypress from opening and closing)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal?.style.display !== 'none') {
      // Prevent the same Escape key that opened the modal from also closing it
      // by requiring at least 100ms to have passed since the modal was opened
      if (Date.now() - confirmModalOpenedAt < 100) {
        return;
      }
      e.stopPropagation();
      closeConfirmModal(false);
    }
  });

  // Enter to confirm (when modal is open, with debounce)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && modal?.style.display !== 'none') {
      // Prevent accidental confirmation right after modal opens
      if (Date.now() - confirmModalOpenedAt < 100) {
        return;
      }
      e.preventDefault();
      closeConfirmModal(true);
    }
  });
}

// ============================================
// Toast Notifications
// ============================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: 'check-circle',
    error: 'alert-circle',
    info: 'info'
  };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <div class="toast-icon">
      <i data-lucide="${icons[type] || 'info'}"></i>
    </div>
    <div class="toast-message">${escapeHtml(message)}</div>
    <button class="toast-close">
      <i data-lucide="x"></i>
    </button>
  `;

  container.appendChild(toast);
  refreshIcons(toast);

  // Close button
  toast.querySelector('.toast-close').addEventListener('click', () => {
    removeToast(toast);
  });

  // Auto remove after 4 seconds
  setTimeout(() => removeToast(toast), 4000);
}

function removeToast(toast) {
  if (!toast.parentElement) return;
  toast.classList.add('hiding');
  setTimeout(() => toast.remove(), ANIMATION.normal);
}

// ============================================
// Event Listeners Setup
// ============================================
function setupEventListeners() {
  // Global keyboard
  document.addEventListener('keydown', handleGlobalKeydown);

  // Click on empty space to clear selection
  // Works on app-main, todo-frame, todo-tree, and app-container
  document.addEventListener('click', (e) => {
    // Don't clear if clicking on a todo item or its children
    if (e.target.closest('.todo-item')) return;

    // Don't clear if clicking on interactive elements
    if (e.target.closest('button, input, select, textarea, a, .modal-overlay, .header-actions, .header-controls, .add-task-btn')) return;

    // Clear selection when clicking on empty space
    const clickableAreas = ['.app-main', '.todo-frame', '.todo-tree', '.app-container', '.app'];
    const isEmptySpace = clickableAreas.some(selector => e.target.closest(selector));

    if (isEmptySpace && state.selectedTaskId) {
      clearSelection();
    }
  });

  // Search
  const searchInput = document.getElementById('search-input');
  searchInput?.addEventListener('input', debounce((e) => {
    handleSearch(e.target.value);
  }, 300));

  searchInput?.addEventListener('focus', () => {
    searchInput.parentElement?.classList.add('focused');
  });

  searchInput?.addEventListener('blur', () => {
    searchInput.parentElement?.classList.remove('focused');
  });

  document.getElementById('search-clear')?.addEventListener('click', () => {
    searchInput.value = '';
    handleSearch('');
    searchInput.focus();
  });

  // Filter dropdown
  filterBtnEl = document.getElementById('filter-btn');
  filterDropdownEl = document.querySelector('.filter-dropdown');
  filterMenuEl = document.getElementById('filter-menu');

  filterBtnEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (filterDropdownEl?.classList.contains('open')) {
      closeFilterMenu();
    } else {
      openFilterMenu();
    }
  });

  document.querySelectorAll('.filter-option').forEach(opt => {
    opt.addEventListener('click', () => setFilter(opt.dataset.filter));
  });

  // Close only when clicking outside button + menu (so menu options can be clicked)
  document.addEventListener('click', (e) => {
    if (!filterDropdownEl || !filterMenuEl || !filterBtnEl) return;
    const target = e.target;
    if (filterBtnEl.contains(target) || filterMenuEl.contains(target)) return;
    closeFilterMenu();
  });

  // Keep the portal menu aligned on scroll/resize (captures scroll on containers too)
  window.addEventListener('resize', () => {
    if (filterMenuEl?.classList.contains('open')) positionFilterMenu();
  });
  window.addEventListener('scroll', () => {
    if (filterMenuEl?.classList.contains('open')) positionFilterMenu();
  }, true);

  // Header actions
  document.getElementById('expand-all-btn')?.addEventListener('click', expandAll);
  document.getElementById('collapse-all-btn')?.addEventListener('click', collapseAll);
  document.getElementById('undo-btn')?.addEventListener('click', handleUndo);
  document.getElementById('redo-btn')?.addEventListener('click', handleRedo);

  // Add task button - opens full create modal
  document.getElementById('add-task-btn')?.addEventListener('click', () => openCreateTaskModal());

  // Task modal - X and Cancel go through the unsaved-changes guard, same as
  // Esc and clicking outside (only prompts when the form is actually dirty)
  document.getElementById('modal-close')?.addEventListener('click', () => tryCloseTaskModal());
  document.getElementById('modal-cancel')?.addEventListener('click', () => tryCloseTaskModal());
  document.getElementById('modal-save')?.addEventListener('click', saveTaskModal);
  document.getElementById('modal-delete')?.addEventListener('click', deleteTaskFromModal);

  // Enter key in task modal triggers Save (except when in textarea)
  document.getElementById('task-modal')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.target.matches('textarea')) {
      e.preventDefault();
      saveTaskModal();
    }
  });

  document.getElementById('modal-status-btn')?.addEventListener('click', async () => {
    // Works in both create and edit modes
    const statusSelect = document.getElementById('modal-status-select');
    statusSelect.value = statusSelect.value === 'completed' ? 'pending' : 'completed';

    const btn = document.getElementById('modal-status-btn');
    const isCompleted = statusSelect.value === 'completed';
    btn.classList.toggle('checked', isCompleted);
    btn.innerHTML = `<i data-lucide="${isCompleted ? 'check-circle-2' : 'circle'}"></i>`;
    refreshIcons(btn);
  });

  document.getElementById('add-subtask-btn')?.addEventListener('click', () => {
    if (currentModalTaskId) {
      // Save the parent task ID before closing modal
      const parentTaskId = currentModalTaskId;

      // Close modal without animation (instant) to avoid state conflicts
      const modal = document.getElementById('task-modal');
      modal.style.display = 'none';
      currentModalTaskId = null;
      modalMode = 'edit';
      createTaskParentId = null;

      // Now open create modal with the saved parent ID
      openCreateTaskModal(parentTaskId);
    }
  });

  document.getElementById('file-upload')?.addEventListener('change', (e) => {
    handleFileUpload(e.target.files);
    e.target.value = '';
  });

  // Description view/edit toggle
  document.getElementById('description-toggle-btn')?.addEventListener('click', toggleDescriptionMode);

  // Click outside modal to close (with proper drag handling)
  // Track where mousedown started to prevent drag-from-inside closing the modal
  document.getElementById('task-modal')?.addEventListener('mousedown', (e) => {
    modalMouseDownTarget = e.target;
  });

  document.getElementById('task-modal')?.addEventListener('mouseup', (e) => {
    // Only close if BOTH mousedown AND mouseup occurred on the overlay
    // This prevents closing when dragging from inside to outside
    if (
      modalMouseDownTarget?.classList.contains('modal-overlay') &&
      e.target.classList.contains('modal-overlay')
    ) {
      tryCloseTaskModal();
    }
    modalMouseDownTarget = null;
  });

  // Shortcuts modal
  document.getElementById('shortcuts-modal')?.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
      toggleShortcutsModal();
    }
  });

  document.getElementById('shortcuts-close')?.addEventListener('click', toggleShortcutsModal);

  // Window resize handler for responsive adjustments
  window.addEventListener('resize', debounce(() => {
    // Re-render if needed for responsive layout changes
  }, 250));

  // Handle dragover on the todo-tree container (for gaps between items)
  // This prevents the "not-allowed" cursor when dragging over empty space
  const todoTree = document.getElementById('todo-tree');
  todoTree?.addEventListener('dragover', (e) => {
    // Only handle if we're actively dragging a task
    if (state.draggedId) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }
  });
}

// ============================================
// Initialization
// ============================================
async function init() {
  console.log('🌙 Soy Lunita - Initializing...');

  // Initialize Lucide icons
  lucide.createIcons();

  // Initialize marked.js for markdown rendering
  initializeMarked();

  // Setup markdown checkbox interactivity
  setupMarkdownCheckboxHandler();

  // Setup smooth floating description toggle button
  smoothStickyToggle.init();

  // Initialize date picker
  datePicker.init();

  // Setup event listeners
  setupEventListeners();

  // Setup confirmation modal listeners
  setupConfirmModalListeners();

  // Initialize filter UI with loaded value from storage
  initializeFilterUI();

  // Connect WebSocket
  connectWebSocket();

  // Load tasks
  await loadTasks();

  console.log('✨ Soy Lunita - Ready!');
}

/**
 * Initialize the filter UI to match the loaded filter state
 */
function initializeFilterUI() {
  const filter = state.currentFilter;

  // Update filter options to show active state
  document.querySelectorAll('.filter-option').forEach(opt => {
    opt.classList.toggle('active', opt.dataset.filter === filter);
  });

  // Update filter label
  const filterLabel = document.getElementById('filter-label');
  if (filterLabel) {
    filterLabel.textContent = filter === 'all' ? 'All' : STATUS_LABELS[filter] || filter.replace('_', ' ');
  }
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

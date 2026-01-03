import workflowsData from '../workflows/n8n_workflows_full.json';

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  nodes?: any[];
  connections?: any;
  [key: string]: any;
}

// Fetch workflows from the local JSON file
export async function fetchWorkflows(): Promise<Workflow[]> {
  try {
    return workflowsData as Workflow[];
  } catch (error) {
    console.error('Error loading workflows:', error);
    return [];
  }
}

// Prefetch and store workflows (for compatibility)
export async function prefetchAndStoreWorkflows(): Promise<void> {
  try {
    const workflows = await fetchWorkflows();
    console.log(`Loaded ${workflows.length} workflows from local storage`);
  } catch (error) {
    console.error('Error prefetching workflows:', error);
  }
}

export default { fetchWorkflows, prefetchAndStoreWorkflows };

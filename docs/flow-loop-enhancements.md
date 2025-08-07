# Flow Loop Enhancements

## Overview

This document outlines potential enhancements to the Agent Mesh SDK's flow orchestration system to support looping patterns. These improvements would enable complex workflows with feedback cycles, revision loops, and conditional processing that are common in multi-agent systems.

## Current State

The existing `FlowExecutionEngine` supports:
- Dependency-based agent execution (DAG - Directed Acyclic Graph)
- Parallel and sequential processing
- Health checks and retry mechanisms
- Message routing between agents

**Limitation**: No native support for loops or feedback cycles between agents.

## Proposed Loop Enhancement Strategies

### 1. Agent-Level Internal Loops (Recommended for MVP)

**Approach**: Handle loops within individual agents rather than at the flow level.

**Benefits**:
- No changes to existing flow engine required
- Simple to implement and debug
- Each agent controls its own loop logic
- Compatible with current architecture

**Implementation Pattern**:
```python
class TranslateAuditLoopAgent:
    """Agent that internally handles translate → audit → revise cycles."""
    
    async def process_message(self, message):
        chunk = message  # Input chunk to process
        max_revision_cycles = 5
        
        # Initial translation
        translated = await self._call_agent("translate_worker", {
            "content": chunk["content"],
            "instructions": "Translate this text accurately"
        })
        
        # Audit and revision loop
        for revision_cycle in range(max_revision_cycles):
            # Audit the translation
            audit_result = await self._call_agent("audit_worker", {
                "original": chunk["content"],
                "translated": translated["content"],
                "revision_cycle": revision_cycle
            })
            
            # Check if revision needed
            if not audit_result.get("needs_revision", False):
                break  # Translation approved
                
            # Request revision with feedback
            translated = await self._call_agent("translate_worker", {
                "content": chunk["content"],
                "previous_translation": translated["content"],
                "feedback": audit_result["feedback"],
                "revision_cycle": revision_cycle + 1
            })
        
        return {
            "chunk_id": chunk["id"],
            "original": chunk["content"],
            "final_translation": translated["content"],
            "revision_cycles": revision_cycle,
            "quality_score": audit_result.get("quality_score", 0.0)
        }
```

**Flow Configuration**:
```python
# Simple flow with internal loop agent
flow_config = {
    "name": "Translation with Internal Loops",
    "agents": [
        {
            "agent_name": "google_docs",
            "upstream_agents": [],
            "required": True
        },
        {
            "agent_name": "chunking",
            "upstream_agents": ["google_docs"],
            "required": True
        },
        {
            "agent_name": "translate_audit_loop",  # Handles loops internally
            "upstream_agents": ["chunking"],
            "required": True
        },
        {
            "agent_name": "combine",
            "upstream_agents": ["translate_audit_loop"],
            "required": True
        }
    ]
}
```

### 2. Flow Engine Loop Extensions (Future Enhancement)

**Approach**: Extend the `FlowExecutionEngine` to support native loop configurations.

**Flow Configuration with Loops**:
```python
flow_config_with_loops = {
    "name": "Translation Pipeline with Native Loops",
    "agents": [
        {
            "agent_name": "google_docs",
            "upstream_agents": [],
            "required": True
        },
        {
            "agent_name": "chunking",
            "upstream_agents": ["google_docs"],
            "required": True
        },
        {
            "agent_name": "translate",
            "upstream_agents": ["chunking"],
            "required": True
        },
        {
            "agent_name": "audit",
            "upstream_agents": ["translate"],
            "required": True,
            # Loop configuration
            "loop_config": {
                "enabled": True,
                "loop_back_to": "translate",  # Agent to loop back to
                "condition_field": "needs_revision",  # Field to check
                "max_iterations": 5,
                "break_condition": "quality_score >= 0.9"
            }
        },
        {
            "agent_name": "combine",
            "upstream_agents": ["audit"],
            "required": True
        }
    ]
}
```

**Enhanced Execution Engine Methods**:
```python
class FlowExecutionEngine:
    async def _execute_flow_with_loops(self, flow_id, execution_id, agents, input_data):
        """Execute flow with loop support."""
        
        agent_map = {agent["agent_name"]: agent for agent in agents}
        completed_agents = set()
        agent_results = {}
        loop_iterations = {}  # Track iterations per loop
        
        # Build execution queue starting with start agents
        execution_queue = [agent for agent in agents if not agent.get("upstream_agents", [])]
        
        while execution_queue or len(completed_agents) < len(agents):
            if not execution_queue:
                # Find next ready agents
                ready_agents = [
                    agent for agent in agents 
                    if (agent["agent_name"] not in completed_agents and 
                        self._is_agent_ready(agent, completed_agents, agent_map))
                ]
                execution_queue.extend(ready_agents)
                
                if not execution_queue:
                    break
            
            # Execute next batch of agents
            current_batch = execution_queue[:]
            execution_queue.clear()
            
            for agent_config in current_batch:
                agent_name = agent_config["agent_name"]
                
                # Build input and execute agent
                agent_input = self._build_agent_input(agent_config, agent_results, input_data)
                result = await self._execute_agent_with_retry(
                    flow_id, execution_id, agent_config, agent_input
                )
                
                agent_results[agent_name] = result
                
                # Check for loop condition
                loop_config = agent_config.get("loop_config", {})
                if loop_config.get("enabled", False):
                    should_loop = self._should_loop(result, loop_config, agent_name, loop_iterations)
                    
                    if should_loop:
                        # Add loop target back to queue
                        loop_target = loop_config["loop_back_to"]
                        loop_target_config = agent_map[loop_target]
                        
                        # Remove loop target from completed (so it can run again)
                        if loop_target in completed_agents:
                            completed_agents.remove(loop_target)
                        
                        # Add to queue if not already there
                        if loop_target_config not in execution_queue:
                            execution_queue.append(loop_target_config)
                        
                        # Don't mark current agent as completed yet
                        continue
                
                # Mark as completed
                completed_agents.add(agent_name)
        
        return self._build_final_output(agents, agent_results)
    
    def _should_loop(self, result, loop_config, agent_name, loop_iterations):
        """Check if agent should trigger a loop."""
        
        # Check max iterations
        max_iterations = loop_config.get("max_iterations", 10)
        current_iterations = loop_iterations.get(agent_name, 0)
        
        if current_iterations >= max_iterations:
            logger.warning(f"Agent '{agent_name}' reached max loop iterations ({max_iterations})")
            return False
        
        # Check loop condition
        condition_field = loop_config.get("condition_field")
        if condition_field and result.get(condition_field, False):
            # Increment iteration counter
            loop_iterations[agent_name] = current_iterations + 1
            logger.info(f"Agent '{agent_name}' triggering loop (iteration {current_iterations + 1})")
            return True
        
        # Check break condition
        break_condition = loop_config.get("break_condition")
        if break_condition:
            # Simple condition evaluation (could be enhanced with expression parser)
            if "quality_score" in break_condition:
                quality_score = result.get("quality_score", 0.0)
                if ">=" in break_condition:
                    threshold = float(break_condition.split(">=")[1].strip())
                    if quality_score >= threshold:
                        return False
        
        return False
```

### 3. Sub-Flow Loop Patterns (Advanced)

**Approach**: Create reusable sub-flows that can loop independently.

**Implementation**:
```python
class SubFlowManager:
    async def execute_translation_chunk_with_loop(self, chunk_data):
        """Execute a sub-flow for a single chunk with loops."""
        
        # Sub-flow configuration for one chunk
        chunk_flow_config = {
            "name": f"Chunk Translation Loop - {chunk_data['chunk_id']}",
            "agents": [
                {
                    "agent_name": "translate_worker",
                    "upstream_agents": [],
                    "required": True
                },
                {
                    "agent_name": "audit_worker", 
                    "upstream_agents": ["translate_worker"],
                    "required": True,
                    "loop_config": {
                        "enabled": True,
                        "loop_back_to": "translate_worker",
                        "condition_field": "needs_revision",
                        "max_iterations": 5
                    }
                }
            ]
        }
        
        # Create and execute sub-flow
        sub_flow_id = await self.create_flow(chunk_flow_config)
        result = await self.execute_flow(sub_flow_id, chunk_data)
        await self.cleanup_flow(sub_flow_id)
        
        return result

# Main orchestrator uses sub-flows
class TranslationOrchestrator:
    async def process_message(self, message):
        chunks = message["chunks"]
        sub_flow_manager = SubFlowManager()
        
        # Process each chunk with its own looping sub-flow
        tasks = [
            sub_flow_manager.execute_translation_chunk_with_loop(chunk)
            for chunk in chunks
        ]
        
        results = await asyncio.gather(*tasks)
        return {"processed_chunks": results}
```

## Use Case Examples

### Document Translation Pipeline with Flexible Chunking and Loops

**Scenario**: Process a document with variable number of chunks, each requiring translation → audit → revision cycles.

**Implementation**:
```python
# 1. Chunking Agent - Returns variable chunks
class ChunkingAgent:
    def process_message(self, message):
        long_text = message["content"]
        
        # Dynamic chunking based on content
        chunks = self.smart_chunk(long_text)
        
        return {
            "chunks": [
                {"id": i+1, "content": chunk} 
                for i, chunk in enumerate(chunks)
            ],
            "total_chunks": len(chunks)
        }
    
    def smart_chunk(self, text):
        # Intelligent chunking based on:
        # - Paragraph breaks, sentence boundaries
        # - Maximum chunk size, semantic boundaries
        max_chunk_size = 1000
        chunks = []
        
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk + paragraph) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

# 2. Translation Orchestrator with Internal Loops
class TranslationOrchestratorWithLoops:
    def __init__(self):
        self.translate_workers = ["translate_worker_1", "translate_worker_2", "translate_worker_3"]
        self.audit_workers = ["audit_worker_1", "audit_worker_2", "audit_worker_3"]
    
    async def process_message(self, message):
        chunks = message["chunks"]
        total_chunks = message["total_chunks"]
        
        logger.info(f"Processing {total_chunks} chunks with {len(self.translate_workers)} workers")
        
        # Process chunks in parallel with loops
        processed_chunks = await self.process_all_chunks_with_loops(chunks)
        
        return {
            "processed_chunks": processed_chunks,
            "total_processed": len(processed_chunks)
        }
    
    async def process_all_chunks_with_loops(self, chunks):
        # Create semaphore to limit concurrent processing
        max_concurrent = min(len(self.translate_workers), len(chunks))
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Process all chunks concurrently with internal loops
        tasks = [
            self.process_single_chunk_with_loop(chunk, semaphore)
            for chunk in chunks
        ]
        
        results = await asyncio.gather(*tasks)
        return results
    
    async def process_single_chunk_with_loop(self, chunk, semaphore):
        async with semaphore:
            return await self.process_chunk_with_revision_loop(chunk)
    
    async def process_chunk_with_revision_loop(self, chunk):
        # Get available workers
        translate_worker = self.get_next_worker(self.translate_workers)
        audit_worker = self.get_next_worker(self.audit_workers)
        
        # Initial translation
        translated = await self.call_agent(translate_worker, chunk)
        
        # Audit and revision loop
        max_revisions = 3
        revision_count = 0
        
        while revision_count < max_revisions:
            audited = await self.call_agent(audit_worker, translated)
            
            if not audited.get("needs_revision", False):
                break  # Audit passed
                
            # Revision needed
            translated = await self.call_agent(translate_worker, {
                **chunk,
                "revision_feedback": audited["feedback"],
                "previous_translation": translated["content"]
            })
            revision_count += 1
        
        return {
            "chunk_id": chunk["id"],
            "original": chunk["content"],
            "final_translation": translated["content"],
            "revision_count": revision_count,
            "audit_passed": True,
            "quality_score": audited.get("quality_score", 0.0)
        }

# 3. Simple Flow Configuration
flexible_translation_flow = {
    "name": "Flexible Document Translation with Loops",
    "agents": [
        {
            "agent_name": "google_docs",
            "upstream_agents": [],
            "required": True
        },
        {
            "agent_name": "chunking", 
            "upstream_agents": ["google_docs"],
            "required": True
        },
        {
            "agent_name": "translation_orchestrator_with_loops",
            "upstream_agents": ["chunking"],
            "required": True
        },
        {
            "agent_name": "combine",
            "upstream_agents": ["translation_orchestrator_with_loops"], 
            "required": True
        }
    ]
}
```

## Implementation Benefits

### Agent-Level Loops (Recommended)
✅ **Immediate Implementation** - Works with current flow engine  
✅ **Simple Debugging** - Loop logic contained within single agent  
✅ **Flexible Control** - Each agent manages its own loop conditions  
✅ **No Breaking Changes** - Compatible with existing flows  
✅ **Easy Testing** - Loop logic can be tested independently  

### Flow Engine Extensions (Future)
⚠️ **Complex Implementation** - Requires significant flow engine changes  
⚠️ **Debugging Complexity** - Loop state spans multiple agents  
✅ **Declarative Configuration** - Loops defined in flow config  
✅ **Visual Flow Representation** - Easier to understand in UI  
✅ **Centralized Loop Management** - Platform controls all loop logic  

## Migration Path

### Phase 1: Agent-Level Loops (MVP)
1. Implement loop-capable agents using internal logic
2. Create examples for common loop patterns
3. Document best practices for loop implementation
4. Test with real-world use cases

### Phase 2: Flow Engine Enhancement (Future)
1. Design loop configuration schema
2. Extend FlowExecutionEngine with loop support
3. Add loop visualization to flow management UI
4. Migrate existing loop agents to use native flow loops
5. Add advanced loop features (conditional routing, complex break conditions)

### Phase 3: Advanced Loop Patterns (Future)
1. Sub-flow loop support
2. Nested loop capabilities
3. Loop performance optimization
4. Loop monitoring and analytics

## Considerations

### Performance
- **Memory Usage**: Loop iterations store intermediate results
- **Execution Time**: Loops can significantly increase processing time
- **Resource Management**: Need to prevent infinite loops and resource exhaustion

### Monitoring
- **Loop Metrics**: Track iteration counts, success rates, performance
- **Debugging Tools**: Visibility into loop state and progression
- **Alerting**: Detect stuck loops or performance degradation

### Error Handling
- **Loop Failure Recovery**: How to handle failures within loops
- **Partial Results**: Save intermediate results even if loop fails
- **Timeout Management**: Prevent loops from running indefinitely

## Conclusion

For the immediate need to support loops in the Agent Mesh SDK, **Agent-Level Internal Loops** provide the best balance of functionality, simplicity, and compatibility. This approach allows complex workflows with feedback cycles while maintaining the existing flow architecture.

Future enhancements can add native flow-level loop support for more complex orchestration patterns, but the agent-level approach provides a solid foundation that meets current requirements without architectural changes.
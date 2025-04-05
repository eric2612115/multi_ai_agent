"""Content verification task handler.

This module provides the handler for content verification tasks.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from forest.models import ReflectionTask
from forest.reflection.handlers.base import TaskHandler
from common.exceptions import ExecutionError
from common.decorators import handle_errors

logger = logging.getLogger(__name__)

class ContentVerificationHandler(TaskHandler):
    """Handler for content verification tasks."""
    
    @property
    def task_type(self) -> str:
        """Get the task type this handler supports."""
        return "content_verification"
    
    @handle_errors(error_type=ExecutionError)
    async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
        """Handle content verification task."""
        result = {
            "success": False,
            "nodes_verified": 0,
            "verified_node_ids": [],
            "issues_found": []
        }
        
        # Get node IDs to verify
        node_ids = task.parameters.get("node_ids", task.target_node_ids)
        
        # If no specific nodes, find candidates with low certainty
        if not node_ids:
            candidates = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "verification_status": "unverified",
                    "certainty_score": {"$lt": 0.7}  # Only uncertain nodes
                },
                projection={"_id": 1},
                limit=10  # Reasonable limit
            )
            
            node_ids = [node["_id"] for node in candidates]
        
        # If no candidates, return empty result
        if not node_ids:
            result["message"] = "No nodes found for verification"
            result["success"] = True
            return result
            
        # Verify the nodes
        verified_nodes = []
        issues = []
        
        for node_id in node_ids:
            verified, issue = await self._verify_node_content(user_id, node_id)
            if verified:
                verified_nodes.append(node_id)
            if issue:
                issues.append({"node_id": node_id, "issue": issue})
                
        # Update result
        result["success"] = True
        result["nodes_verified"] = len(verified_nodes)
        result["verified_node_ids"] = verified_nodes
        result["issues_found"] = issues
        
        # Track energy
        self.energy_consumed = task.energy_cost
        
        return result
    
    async def _verify_node_content(self, user_id: str, node_id: str) -> Tuple[bool, Optional[str]]:
        """Verify the content of a node for accuracy and consistency."""
        try:
            # Get the node
            node = await self.storage.get_document("nodes", node_id)
            if not node:
                return False, "Node not found"
                
            # Skip if already verified
            if node.get("verification_status") == "verified":
                return True, None
                
            # Get node data for verification
            label = node.get("label", "Unknown")
            content = node.get("content", "")
            summary = node.get("summary", "")
            
            # If no content to verify, skip
            if not content and not summary:
                return False, "No content to verify"
            
            # Check for internal consistency first
            consistency_issue = await self._check_consistency(label, summary, content)
            if consistency_issue:
                # Update node with issue
                await self.storage.update_document(
                    "nodes",
                    node_id,
                    {
                        "verification_status": "contradicted",
                        "verified_at": datetime.utcnow(),
                        "verified_by": "reflection_system",
                        "updated_at": datetime.utcnow(),
                        "certainty_score": 0.4  # Lower certainty due to issue
                    }
                )
                
                return False, consistency_issue
            
            # If no issues found, mark as verified
            await self.storage.update_document(
                "nodes",
                node_id,
                {
                    "verification_status": "verified",
                    "verified_at": datetime.utcnow(),
                    "verified_by": "reflection_system",
                    "updated_at": datetime.utcnow(),
                    "certainty_score": 0.9  # High certainty after verification
                }
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Failed to verify node {node_id}: {str(e)}")
            return False, f"Verification error: {str(e)}"
    
    async def _check_consistency(self, label: str, summary: str, content: str) -> Optional[str]:
        """Check for internal consistency issues in node content."""
        # If either summary or content is missing, no consistency to check
        if not summary or not content:
            return None
            
        # Prepare the prompt
        prompt = f"""Please check the following content for internal consistency issues:

        Title: {label}
        
        Summary: {summary}
        
        Content: {content}
        
        Are there any contradictions, factual inconsistencies, or logical problems between 
        the title, summary, and content? If yes, please describe the specific issues.
        If no inconsistencies are found, respond with "No inconsistencies found."
        """
        
        # Get the response
        response = await self.text_model.generate_text(prompt, max_tokens=300)
        
        # Parse the response
        if "no inconsistencies" in response.lower() or "no issues" in response.lower():
            return None
        else:
            return response.strip()

#!/usr/bin/env python3
"""
GitHub Issue Creator for PowerTrader AI+ Development

This script helps create GitHub issues from the TODO.md file to set up
the project management system. It can be run manually or integrated
into GitHub Actions for automated project management.

Usage:
    python scripts/create_github_issues.py --token YOUR_GITHUB_TOKEN
"""

import argparse
import json
import re
import sys
from typing import Any, Dict, List

import requests


class GitHubIssueCreator:
    def __init__(self, repo_owner: str, repo_name: str, token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def parse_todo_file(self, todo_path: str = "TODO.md") -> List[Dict[str, Any]]:
        """Parse TODO.md file and extract tasks with metadata."""
        tasks = []
        current_phase = ""
        current_category = ""

        with open(todo_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Detect phase headers
            if line.startswith("### Phase"):
                current_phase = line.replace("### ", "").split(":")[0]
                i += 1
                continue

            # Detect category headers
            if line.startswith("#### "):
                current_category = line.replace("#### ", "")
                i += 1
                continue

            # Detect task items
            if line.startswith("- [ ] **"):
                task_title = re.search(r"\*\*(.*?)\*\*", line)
                if task_title:
                    title = task_title.group(1)

                    # Collect task description
                    description_lines = []
                    j = i + 1
                    while j < len(lines) and lines[j].startswith("  - "):
                        description_lines.append(lines[j].strip()[4:])  # Remove "  - "
                        j += 1

                    # Determine priority and labels
                    priority = self._get_priority_from_phase(current_phase)
                    labels = self._get_labels_from_content(
                        current_phase, current_category, title, description_lines
                    )

                    task = {
                        "title": f"[TASK] {title}",
                        "body": self._create_issue_body(
                            current_phase, current_category, title, description_lines
                        ),
                        "labels": labels,
                        "milestone": self._get_milestone_from_phase(current_phase),
                    }

                    tasks.append(task)
                    i = j - 1

            i += 1

        return tasks

    def _get_priority_from_phase(self, phase: str) -> str:
        """Determine priority based on phase."""
        phase_priorities = {
            "Phase 1": "priority-critical",
            "Phase 2": "priority-high",
            "Phase 3": "priority-medium",
            "Phase 4": "priority-low",
        }
        return phase_priorities.get(phase, "priority-medium")

    def _get_labels_from_content(
        self, phase: str, category: str, title: str, description: List[str]
    ) -> List[str]:
        """Extract appropriate labels based on content."""
        labels = ["task", "development"]

        # Phase labels
        phase_map = {
            "Phase 1": "phase-1-critical",
            "Phase 2": "phase-2-functional",
            "Phase 3": "phase-3-production",
            "Phase 4": "phase-4-optimization",
        }
        if phase in phase_map:
            labels.append(phase_map[phase])

        # Priority
        labels.append(self._get_priority_from_phase(phase))

        # Component labels based on content
        content_text = f"{title} {category} {' '.join(description)}".lower()

        if any(
            word in content_text
            for word in ["credential", "security", "authentication", "encryption"]
        ):
            labels.append("component-security")
        if any(word in content_text for word in ["trading", "order", "execution"]):
            labels.append("component-trading")
        if any(word in content_text for word in ["risk", "portfolio", "position"]):
            labels.append("component-risk")
        if any(word in content_text for word in ["gui", "interface", "ui"]):
            labels.append("component-ui")
        if any(word in content_text for word in ["database", "db", "migration"]):
            labels.append("component-database")
        if any(word in content_text for word in ["api", "integration", "endpoint"]):
            labels.append("component-api")
        if any(word in content_text for word in ["analytics", "reporting", "metrics"]):
            labels.append("component-analytics")
        if any(word in content_text for word in ["test", "testing", "coverage"]):
            labels.append("component-testing")

        # Security-specific labeling
        if any(
            word in content_text
            for word in ["security", "vulnerability", "credential", "encryption"]
        ):
            labels.append("security")

        return labels

    def _get_milestone_from_phase(self, phase: str) -> str:
        """Get milestone name from phase."""
        milestone_map = {
            "Phase 1": "Phase 1: Security & Stability Foundation",
            "Phase 2": "Phase 2: Core Functionality Complete",
            "Phase 3": "Phase 3: Production Deployment Ready",
            "Phase 4": "Phase 4: Enterprise Scale",
        }
        return milestone_map.get(phase, "")

    def _create_issue_body(
        self, phase: str, category: str, title: str, description: List[str]
    ) -> str:
        """Create formatted issue body."""
        body = f"""## Task Overview
{title}

## TODO Reference
- **Phase**: {phase}
- **Category**: {category}
- **Priority**: {self._get_priority_from_phase(phase).replace('priority-', '').title()}

## Technical Details
### Implementation Approach
{chr(10).join(f'- {desc}' for desc in description) if description else 'Implementation details to be determined during task planning.'}

## Acceptance Criteria
- [ ] Implementation completed and working
- [ ] Tests written and passing
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] No security vulnerabilities introduced
- [ ] Performance impact assessed

## Dependencies
<!-- List any tasks that must be completed before this one -->

## Testing Requirements
- [ ] Unit tests written
- [ ] Integration tests updated (if applicable)
- [ ] Manual testing completed
- [ ] Security testing (if applicable)
- [ ] Performance testing (if applicable)

## Definition of Done
- [ ] Code implemented and working
- [ ] Tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] No security vulnerabilities introduced
- [ ] Performance impact assessed

## Risk Assessment
- [ ] Low risk (isolated change)
- [ ] Medium risk (affects multiple components)
- [ ] High risk (critical system changes)

---
*This issue was automatically generated from TODO.md. See [Development Workflow](.github/DEVELOPMENT_WORKFLOW.md) for process details.*"""

        return body

    def create_milestone(
        self, title: str, description: str, due_date: str = None
    ) -> bool:
        """Create a milestone if it doesn't exist."""
        # Check if milestone exists
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/milestones"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            existing_milestones = response.json()
            for milestone in existing_milestones:
                if milestone["title"] == title:
                    print(f"✓ Milestone '{title}' already exists")
                    return True

        # Create milestone
        milestone_data = {
            "title": title,
            "description": description,
            "due_on": due_date,
        }

        response = requests.post(url, headers=self.headers, json=milestone_data)

        if response.status_code == 201:
            print(f"✓ Created milestone: {title}")
            return True
        else:
            print(f"✗ Failed to create milestone: {title} - {response.text}")
            return False

    def create_labels(self) -> bool:
        """Create project labels if they don't exist."""
        labels_config = [
            # Priority Labels
            {
                "name": "priority-critical",
                "color": "d73a49",
                "description": "Critical issues requiring immediate attention",
            },
            {
                "name": "priority-high",
                "color": "fb8500",
                "description": "High priority issues",
            },
            {
                "name": "priority-medium",
                "color": "ffb627",
                "description": "Medium priority issues",
            },
            {
                "name": "priority-low",
                "color": "28a745",
                "description": "Low priority issues",
            },
            # Phase Labels
            {
                "name": "phase-1-critical",
                "color": "d73a49",
                "description": "Phase 1: Security & Stability",
            },
            {
                "name": "phase-2-functional",
                "color": "fb8500",
                "description": "Phase 2: Functional Completeness",
            },
            {
                "name": "phase-3-production",
                "color": "007bff",
                "description": "Phase 3: Production Readiness",
            },
            {
                "name": "phase-4-optimization",
                "color": "28a745",
                "description": "Phase 4: Scalability & Optimization",
            },
            # Component Labels
            {
                "name": "component-security",
                "color": "d73a49",
                "description": "Security-related changes",
            },
            {
                "name": "component-trading",
                "color": "28a745",
                "description": "Trading functionality",
            },
            {
                "name": "component-risk",
                "color": "fb8500",
                "description": "Risk management",
            },
            {
                "name": "component-ui",
                "color": "007bff",
                "description": "User interface",
            },
            {
                "name": "component-database",
                "color": "6f42c1",
                "description": "Database operations",
            },
            {
                "name": "component-api",
                "color": "20c997",
                "description": "API integration",
            },
            {
                "name": "component-analytics",
                "color": "fd7e14",
                "description": "Analytics and reporting",
            },
            {
                "name": "component-testing",
                "color": "6c757d",
                "description": "Testing framework",
            },
            # Status Labels
            {
                "name": "needs-triage",
                "color": "ededed",
                "description": "Needs initial review",
            },
            {
                "name": "blocked",
                "color": "d73a49",
                "description": "Blocked by dependencies",
            },
            {
                "name": "urgent",
                "color": "b60205",
                "description": "Requires immediate attention",
            },
        ]

        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/labels"

        # Get existing labels
        response = requests.get(url, headers=self.headers)
        existing_labels = (
            {label["name"] for label in response.json()}
            if response.status_code == 200
            else set()
        )

        for label_config in labels_config:
            if label_config["name"] in existing_labels:
                print(f"✓ Label '{label_config['name']}' already exists")
                continue

            response = requests.post(url, headers=self.headers, json=label_config)
            if response.status_code == 201:
                print(f"✓ Created label: {label_config['name']}")
            else:
                print(
                    f"✗ Failed to create label: {label_config['name']} - {response.text}"
                )

        return True

    def create_milestones(self) -> bool:
        """Create project milestones."""
        milestones = [
            {
                "title": "Phase 1: Security & Stability Foundation",
                "description": "Resolve critical security vulnerabilities and implement robust error handling",
                "due_date": None,  # Set dates as needed
            },
            {
                "title": "Phase 2: Core Functionality Complete",
                "description": "Complete trading functionality and risk management systems",
                "due_date": None,
            },
            {
                "title": "Phase 3: Production Deployment Ready",
                "description": "Achieve production deployment readiness with compliance",
                "due_date": None,
            },
            {
                "title": "Phase 4: Enterprise Scale",
                "description": "Optimize for enterprise-scale deployment",
                "due_date": None,
            },
        ]

        for milestone in milestones:
            self.create_milestone(
                milestone["title"], milestone["description"], milestone["due_date"]
            )

        return True

    def create_issue(self, issue_data: Dict[str, Any]) -> bool:
        """Create a single GitHub issue."""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/issues"

        response = requests.post(url, headers=self.headers, json=issue_data)

        if response.status_code == 201:
            issue = response.json()
            print(f"✓ Created issue: {issue['title']} (#{issue['number']})")
            return True
        else:
            print(f"✗ Failed to create issue: {issue_data['title']} - {response.text}")
            return False

    def setup_project(self, todo_path: str = "TODO.md", dry_run: bool = False) -> bool:
        """Set up the entire project with labels, milestones, and issues."""
        print("🚀 Setting up PowerTrader AI+ GitHub Project...")

        if not dry_run:
            # Create labels and milestones
            print("\n📋 Creating labels...")
            self.create_labels()

            print("\n🎯 Creating milestones...")
            self.create_milestones()

        # Parse TODO and create issues
        print(f"\n📝 Parsing {todo_path}...")
        tasks = self.parse_todo_file(todo_path)
        print(f"Found {len(tasks)} tasks to create")

        if dry_run:
            print("\n🔍 DRY RUN - Issues that would be created:")
            for i, task in enumerate(tasks, 1):
                print(f"{i:2d}. {task['title']}")
                print(f"    Labels: {', '.join(task['labels'])}")
                print(f"    Milestone: {task['milestone']}")
                print()
        else:
            print("\n📋 Creating issues...")
            created_count = 0
            for task in tasks:
                if self.create_issue(task):
                    created_count += 1

            print(
                f"\n✅ Project setup complete! Created {created_count}/{len(tasks)} issues."
            )

        return True


def main():
    parser = argparse.ArgumentParser(description="Create GitHub issues from TODO.md")
    parser.add_argument("--token", required=True, help="GitHub personal access token")
    parser.add_argument("--repo", default="PowerTrader_AI", help="Repository name")
    parser.add_argument(
        "--owner", help="Repository owner (will prompt if not provided)"
    )
    parser.add_argument("--todo-path", default="TODO.md", help="Path to TODO.md file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without actually creating",
    )

    args = parser.parse_args()

    # Get repository owner if not provided
    if not args.owner:
        args.owner = input(
            "Enter GitHub repository owner (username or organization): "
        ).strip()
        if not args.owner:
            print("Repository owner is required")
            sys.exit(1)

    # Create issue creator
    creator = GitHubIssueCreator(args.owner, args.repo, args.token)

    try:
        creator.setup_project(args.todo_path, args.dry_run)
    except FileNotFoundError:
        print(f"Error: TODO.md file not found at {args.todo_path}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: GitHub API request failed - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
GitHub GraphQL Queries
"""

ISSUE_FIELDS = """
number
title
body
state
stateReason
url
createdAt
updatedAt
closedAt
author {
  login
  avatarUrl
  ... on User {
    name
    email
  }
}
assignees(first: 10) {
  nodes {
    login
    avatarUrl
    ... on User {
      name
      email
    }
  }
}
comments(first: 50) {
  nodes {
    author {
      login
      avatarUrl
      ... on User {
        name
        email
      }
    }
    body
    createdAt
    updatedAt
  }
}
"""

PULL_REQUEST_FIELDS = """
number
title
body
state
merged
changedFiles
url
createdAt
updatedAt
mergedAt
closedAt
baseRefName
headRefName
author {
  __typename
  login
  avatarUrl
  url
  ... on User {
    databaseId
    name
    email
  }
}
mergedBy {
  __typename
  login
  avatarUrl
  url
  ... on User {
    databaseId
    name
    email
  }
}
assignees(first: 10) {
  nodes {
    __typename
    login
    avatarUrl
    url
    ... on User {
      databaseId
      name
      email
    }
  }
}
labels(first: 20) {
  nodes {
    name
    color
    description
  }
}
milestone {
  number
  title
  state
  dueOn
}
reviewRequests(first: 10) {
  nodes {
    requestedReviewer {
      ... on User {
        __typename
        databaseId
        login
        name
        email
        avatarUrl
        url
      }
    }
  }
}
isDraft
reviewDecision
additions
deletions
comments(first: 50) {
  nodes {
    databaseId
    author {
      __typename
      login
      avatarUrl
      url
      ... on User {
        databaseId
        name
        email
      }
    }
    body
    createdAt
    updatedAt
  }
}
reviews(first: 10) {
  nodes {
    databaseId
    author {
      __typename
      login
      avatarUrl
      url
      ... on User {
        databaseId
        name
        email
      }
    }
    state
    body
    submittedAt
  }
}
reviewThreads(first: 50) {
  nodes {
    comments(first: 10) {
      nodes {
        databaseId
        author {
          __typename
          login
          avatarUrl
          url
          ... on User {
            databaseId
            name
            email
          }
        }
        body
        path
        line
        originalLine
        outdated
        diffHunk
        createdAt
        updatedAt
      }
    }
  }
}
commits(first: 100) {
  nodes {
    commit {
      oid
      message
      author {
        name
        email
        user {
          __typename
          databaseId
          login
          name
          email
          avatarUrl
          url
        }
      }
      committedDate
    }
  }
}
"""

PULL_REQUESTS_QUERY = f"""
query($owner: String!, $repo: String!, $first: Int!, $after: String) {{
  repository(owner: $owner, name: $repo) {{
    pullRequests(
      first: $first,
      after: $after,
      states: [OPEN, CLOSED, MERGED],
      orderBy: {{field: UPDATED_AT, direction: DESC}}
    ) {{
      pageInfo {{
        hasNextPage
        endCursor
      }}
      nodes {{
        {PULL_REQUEST_FIELDS}
      }}
    }}
  }}
}}
"""

ORG_MEMBERS_QUERY = """
query($org: String!, $first: Int!, $after: String) {
  organization(login: $org) {
    membersWithRole(first: $first, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        role
        node {
          databaseId
          login
          name
          email
          avatarUrl
        }
      }
    }
  }
}
"""

ISSUES_QUERY = f"""
query($owner: String!, $repo: String!, $first: Int!, $after: String) {{
  repository(owner: $owner, name: $repo) {{
    issues(
      first: $first,
      after: $after,
      states: [OPEN, CLOSED],
      orderBy: {{field: UPDATED_AT, direction: DESC}}
    ) {{
      pageInfo {{
        hasNextPage
        endCursor
      }}
      nodes {{
        {ISSUE_FIELDS}
      }}
    }}
  }}
}}
"""


def _build_numbers_query(connection_name: str) -> str:
    states = (
        "[OPEN, CLOSED]"
        if connection_name == "issues"
        else "[OPEN, CLOSED, MERGED]"
    )
    return f"""
query($owner: String!, $repo: String!, $first: Int!, $after: String) {{
  repository(owner: $owner, name: $repo) {{
    {connection_name}(
      first: $first,
      after: $after,
      states: {states},
      orderBy: {{field: UPDATED_AT, direction: DESC}}
    ) {{
      pageInfo {{
        hasNextPage
        endCursor
      }}
      nodes {{
        number
        updatedAt
      }}
    }}
  }}
}}
"""


ISSUE_NUMBERS_QUERY = _build_numbers_query("issues")

PULL_REQUEST_NUMBERS_QUERY = _build_numbers_query("pullRequests")

ISSUE_BY_NUMBER_QUERY = f"""
query($owner: String!, $repo: String!, $number: Int!) {{
  repository(owner: $owner, name: $repo) {{
    issue(number: $number) {{
      {ISSUE_FIELDS}
    }}
  }}
}}
"""

PULL_REQUEST_BY_NUMBER_QUERY = f"""
query($owner: String!, $repo: String!, $number: Int!) {{
  repository(owner: $owner, name: $repo) {{
    pullRequest(number: $number) {{
      {PULL_REQUEST_FIELDS}
    }}
  }}
}}
"""


def build_pull_requests_by_numbers_query(numbers: list[int]) -> str:
    pull_requests = "\n".join(
        f"""
        pr_{number}: pullRequest(number: {number}) {{
          {PULL_REQUEST_FIELDS}
        }}
        """
        for number in numbers
    )
    return f"""
query($owner: String!, $repo: String!) {{
  repository(owner: $owner, name: $repo) {{
    {pull_requests}
  }}
}}
"""

"""
GitHub GraphQL Queries
"""

PULL_REQUESTS_QUERY = """
query($owner: String!, $repo: String!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: $first, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
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
          login
          avatarUrl
          ... on User {
            name
            email
          }
        }
        mergedBy {
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
        labels(first: 20) { nodes { name color description } }
        milestone { number title state dueOn }
        reviewRequests(first: 10) {
          nodes {
            requestedReviewer {
              ... on User { login name email avatarUrl }
            }
          }
        }
        reviews(first: 10) {
          nodes {
            databaseId
            author {
              login
              avatarUrl
              ... on User {
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
                  login
                  avatarUrl
                  ... on User {
                    name
                    email
                  }
                }
                body
                path
                line
                originalLine
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
                user { login }
              }
              committedDate
            }
          }
        }
      }
    }
  }
}
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

ISSUES_QUERY = """
query($owner: String!, $repo: String!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: $first, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
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
      }
    }
  }
}
"""

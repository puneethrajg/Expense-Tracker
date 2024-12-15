// Utility function for making POST requests with JSON body
async function postRequest(url, body) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json', // Ensure Content-Type is application/json
            },
            body: JSON.stringify(body), // Stringify the body to ensure it's valid JSON
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`Backend error: ${errorText}`);
            throw new Error(`Request failed with status ${response.status}`);
        }

        // Check if the response content is JSON
        const contentType = response.headers.get('Content-Type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();  // Parse the JSON if it's valid
        } else {
            throw new Error('Expected JSON response, but got ' + contentType);
        }

    } catch (err) {
        console.error('Error during request:', err);
        alert(`Request failed: ${err.message}`);
        throw err;  // Propagate the error
    }
}

async function startAuthentication() {
    try {
        // Send the user ID along with the request for authentication options
        const userId = 'test_user_id'; // Replace with the actual user ID logic
        const options = await postRequest('/get_authentication_options', { user_id: userId });

        const publicKey = {
            ...options,
            challenge: new Uint8Array(options.challenge),
            allowCredentials: options.allowCredentials.map(cred => ({
                ...cred,
                id: new Uint8Array(cred.id),
            })),
        };

        // Proceed with WebAuthn authentication using the options
        const assertion = await navigator.credentials.get({ publicKey });

        const assertionJSON = {
            id: assertion.id,
            rawId: arrayBufferToBase64(assertion.rawId),
            response: {
                clientDataJSON: arrayBufferToBase64(assertion.response.clientDataJSON),
                authenticatorData: arrayBufferToBase64(assertion.response.authenticatorData),
                signature: arrayBufferToBase64(assertion.response.signature),
            },
        };

        // Send the assertion to the backend for verification
        const res = await postRequest('/verify_biometric', assertionJSON);

        if (res.success) {
            alert('Authentication successful!');
        } else {
            alert('Authentication failed!');
        }
    } catch (err) {
        alert('Authentication failed: ' + err.message);
    }
}


// Helper function to convert ArrayBuffer to Base64
function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const length = bytes.length;

    for (let i = 0; i < length; i++) {
        binary += String.fromCharCode(bytes[i]);
    }

    return window.btoa(binary);
}

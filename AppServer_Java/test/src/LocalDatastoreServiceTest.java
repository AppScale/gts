package src;


import java.io.IOException;
import java.io.Writer;

import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.ResponseHandler;
import org.apache.http.client.methods.HttpUriRequest;
import org.apache.http.impl.client.DefaultHttpClient;
import org.junit.Test;
import org.mockito.ArgumentMatcher;

import static org.mockito.Mockito.*;

import com.google.appengine.api.datastore.dev.HTTPClientDatastoreProxy;
import com.google.appengine.api.datastore.dev.LocalDatastoreService;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.apphosting.api.DatastorePb;
import com.google.storage.onestore.v3.OnestoreEntity.EntityProto;
import com.google.storage.onestore.v3.OnestoreEntity.Path;
import com.google.storage.onestore.v3.OnestoreEntity.Path.Element;
import com.google.storage.onestore.v3.OnestoreEntity.Property;
import com.google.storage.onestore.v3.OnestoreEntity.PropertyValue;
import com.google.storage.onestore.v3.OnestoreEntity.PropertyValue.UserValue;
import com.google.storage.onestore.v3.OnestoreEntity.Reference;


public class LocalDatastoreServiceTest
{

	// @Test
	/*
	 * Ignoring this test for now, there is a limitation where we can't mock out
	 * the static method call in HTTPClientDatastoreProxy in method getUser() so 
	 * UserServiceImpl.getCurrentUser throws a nullpointer
	 */
	public void testPutImpl() throws ClientProtocolException, IOException
	{
		/*
		 * This test puts together the input arguments for putImpl, mocks out
		 * the HTTPClientDatastoreProxy and basically passes if there are no
		 * exceptions thrown. The reason there are no assertions is that neither
		 * the putImpl method or the doPost method return anything.
		 */

		// service with putImpl method
		LocalDatastoreService service = new LocalDatastoreService();

		// 1st arg to putImpl
		Status status = getMockStatus();

		// 2nd arg to putImpl
		DatastorePb.PutRequest request = getMockRequest();

		// mock out HttpClientDatastoreProxy
		HTTPClientDatastoreProxy proxy = new HTTPClientDatastoreProxy("localhost", 8080, false);
		DefaultHttpClient client = mock(DefaultHttpClient.class);
		byte[] bytes = { 1, 2, 3, 4, 5 };
		when(client.execute(any(HttpUriRequest.class), any(ResponseHandler.class))).thenReturn(bytes);
		proxy.setClient(client);
		service.setProxy(proxy);

		// test method
		service.putImpl(status, request);
	}

	public Status getMockStatus()
	{
		Status status = new Status();
		status.setErrorCode(0);
		status.setSuccessful(true);

		return status;
	}

	public DatastorePb.PutRequest getMockRequest()
	{
		/*
		 * See comment at end of this class to see what this request actually
		 * looks like
		 */

		DatastorePb.PutRequest request = new DatastorePb.PutRequest();
		request.setForce(false);
		request.setMarkChanges(false);
		request.setTrusted(false);

		EntityProto ep = new EntityProto();

		Reference ref = new Reference();
		ref.setApp("javabook");
		Path path = new Path();
		Element elem = new Element();
		elem.setType("Greeting");
		path.addElement(elem);
		ref.setPath(path);

		Property contentProp = new Property();
		PropertyValue value;
		contentProp.setName("content");
		value = new PropertyValue();
		value.setStringValue("abcdefg");
		contentProp.setValue(value);
		contentProp.setMultiple(false);

		Property userProperty = new Property();
		userProperty.setName("author");
		PropertyValue userPropertyValue = new PropertyValue();
		UserValue userValue = new UserValue();
		userValue.setEmail("test@example.com");
		userValue.setAuthDomain("gmail.com");
		userValue.setGaiaid(0);
		userValue.setObfuscatedGaiaid("-1405876145");
		userPropertyValue.setUserValue(userValue);
		userProperty.setValue(userPropertyValue);
		userProperty.setMultiple(false);

		Property meaningProp = new Property();
		meaningProp.setMeaning(7);
		meaningProp.setName("date");
		PropertyValue meaningPropValue = new PropertyValue();
		meaningPropValue.setInt64Value(1234567);
		meaningProp.setValue(meaningPropValue);
		meaningProp.setMultiple(false);

		ep.addProperty(contentProp);
		ep.addProperty(userProperty);
		ep.addProperty(meaningProp);
		ep.setKey(ref);

		request.addEntity(ep);

		System.out.println(request.toString());

		return request;
	}

	/*
	 * Sample request entity < key < app: "javabook" path < Element { type:
	 * "Greeting" } > > entity_group <
	 * 
	 * > property < name: "content" value < stringValue: "aafaefaef" > multiple:
	 * false > property < name: "author" value < UserValue { email:
	 * "test@example.com" auth_domain: "gmail.com" gaiaid: 0 obfuscated_gaiaid:
	 * "-1405876145" } > multiple: false > property < meaning: 7 name: "date"
	 * value < int64Value: 0x4cd6276e39108 > multiple: false > >
	 */
}